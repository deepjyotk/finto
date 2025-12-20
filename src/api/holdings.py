"""Holdings API endpoints - depends ONLY on service layer"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.api.schemas.holdings import BulkHoldingsUploadResponse
from src.api.schemas.home import (
    BrokerPayload,
    ChatIntegration,
    HoldingsMetadataSchema,
    PortfolioUpdates,
    WhatsAppPayload,
)
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.dependencies import get_broker_service, get_holdings_service, get_whatsapp_service
from src.services.broker import BrokerService
from src.services.holdings import HoldingsService
from src.services.whatsapp import WhatsAppService

logger = logger_for(__name__)

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("/metadata", response_model=HoldingsMetadataSchema)
async def get_holdings_metadata(
    whatsapp_svc: Annotated[WhatsAppService, Depends(get_whatsapp_service)],
    broker_svc: Annotated[BrokerService, Depends(get_broker_service)],
    holdings_svc: Annotated[HoldingsService, Depends(get_holdings_service)],
    user: dict = Depends(require_auth),
):
    user_id = UUID(user["user_id"])

    try:
        whatsapp_data = await whatsapp_svc.get_whatsapp_data_by_user_id(user_id)

        chat_integrations = []
        if whatsapp_data:
            chat_integrations.append(
                ChatIntegration(
                    whatsapp=WhatsAppPayload(
                        id=whatsapp_data["id"],
                        user_e164=whatsapp_data["user_e164"],
                    )
                )
            )
        else:
            chat_integrations.append(ChatIntegration(whatsapp=None))

        brokers_data = await broker_svc.get_all_brokers()
        available_brokers = [
            BrokerPayload(
                broker_id=broker["broker_id"],
                broker_name=broker["broker_name"],
                broker_type=broker["broker_type"],
                country=broker["country"],
            )
            for broker in brokers_data
        ]

        portfolio_updates_data = await holdings_svc.get_portfolio_updates(user_id)
        portfolio_updates = [
            PortfolioUpdates(
                broker_id=p["broker_id"],
                broker_name=p["broker_name"],
                broker_user_id=p["broker_user_id"],
                last_updated_at=p["last_updated_at"],
                uploaded_via=p["uploaded_via"],
                additional_metadata=p["additional_metadata"],
            )
            for p in portfolio_updates_data
        ]

        return HoldingsMetadataSchema(
            chat_integrations=chat_integrations,
            available_brokers=available_brokers,
            portfolio_updates=portfolio_updates,
        )

    except Exception as e:
        logger.error(f"Error getting holdings metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/file-upload",
    response_model=BulkHoldingsUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk upload equity holdings from file",
    description="Upload Excel (.xlsx, .xls) or CSV file to create multiple equity holdings.",
    responses={
        201: {"description": "Holdings successfully uploaded and created"},
        400: {"description": "Invalid file format or parsing error"},
        401: {"description": "Not authenticated or invalid token"},
    },
)
async def upload_holdings_file(
    broker_id: Annotated[UUID, Form(..., description="Broker ID")],
    file: Annotated[UploadFile, File(..., description="Excel or CSV file with holdings data")],
    svc: Annotated[HoldingsService, Depends(get_holdings_service)],
    broker_svc: Annotated[BrokerService, Depends(get_broker_service)],
    user: dict = Depends(require_auth),
) -> BulkHoldingsUploadResponse:
    """
    Upload and process equity holdings from Excel or CSV file.

    Accepts files in the following formats:
    - Excel (.xlsx, .xls)
    - CSV (.csv)

    Expected columns in the file:
    - Symbol
    - ISIN
    - Sector (optional)
    - Quantity Available
    - Quantity Long Term
    - Quantity Pledged (Margin)
    - Average Price
    - Previous Closing Price

    The broker_id is provided as form data, and user_id is extracted from
    the authenticated user's JWT token.

    **Authentication required**: Yes (JWT token in cookie)

    Returns the number of holdings successfully created.
    """
    logger.info(
        "bulk_holdings_upload_attempt",
        extra={
            "user_id": str(user["user_id"]),
            "broker_id": str(broker_id),
        },
    )

    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    filename_lower = file.filename.lower()
    if not filename_lower.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload .xlsx, .xls, or .csv files.",
        )

    try:
        # Read file content
        file_content = await file.read()

        # Parse file to holdings list using broker service
        holdings_list, discrepancies = await broker_svc.parse_holdings_file(
            file_content=file_content, filename=file.filename, broker_id=broker_id
        )

        logger.info(
            "file_parsed_successfully",
            extra={
                "user_id": str(user["user_id"]),
                "records_count": len(holdings_list),
            },
        )

        # Save all holdings
        records_processed = await svc.save_user_holdings(
            holdings_list=holdings_list, user_id=user["user_id"]
        )

        logger.info(
            "bulk_holdings_upload_success",
            extra={
                "user_id": str(user["user_id"]),
                "broker_id": str(broker_id),
                "records_processed": records_processed,
            },
        )

        message = f"Successfully uploaded {records_processed} holdings"
        if discrepancies:
            symbols_list = ", ".join(discrepancies.keys())
            message += f". Note: Some symbols had issues - {symbols_list}"

        return BulkHoldingsUploadResponse(
            success=True,
            records_processed=records_processed,
            message=message,
        )

    except ValueError as e:
        logger.error(
            "file_parsing_error",
            extra={
                "user_id": str(user["user_id"]),
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "bulk_holdings_upload_error",
            extra={
                "user_id": str(user["user_id"]),
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}",
        )


@router.put(
    "/file-upload/{user_broker_id}",
    response_model=BulkHoldingsUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Update equity holdings from file",
    responses={
        200: {"description": "Holdings successfully updated"},
        400: {"description": "Invalid file format or parsing error"},
        401: {"description": "Not authenticated or invalid token"},
        404: {"description": "Holdings metadata not found"},
    },
)
async def update_holdings_file(
    user_broker_id: UUID,
    file: Annotated[UploadFile, File(..., description="Excel or CSV file with holdings data")],
    svc: Annotated[HoldingsService, Depends(get_holdings_service)],
    broker_svc: Annotated[BrokerService, Depends(get_broker_service)],
    user: dict = Depends(require_auth),
) -> BulkHoldingsUploadResponse:
    logger.info(
        "bulk_holdings_update_attempt",
        extra={
            "user_id": str(user["user_id"]),
            "user_broker_id": str(user_broker_id),
        },
    )

    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    filename_lower = file.filename.lower()
    if not filename_lower.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload .xlsx, .xls, or .csv files.",
        )

    try:
        # Get metadata to retrieve broker_id
        metadata = await svc.repo.get_metadata_by_user_broker_id(
            user_broker_id, UUID(user["user_id"])
        )
        if metadata is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Holdings metadata not found or access denied",
            )

        # Read file content
        file_content = await file.read()

        # Parse file to holdings list using broker service
        holdings_list, discrepancies = await broker_svc.parse_holdings_file(
            file_content=file_content, filename=file.filename, broker_id=metadata.broker_id
        )

        logger.info(
            "file_parsed_successfully",
            extra={
                "user_id": str(user["user_id"]),
                "records_count": len(holdings_list),
            },
        )

        # Upsert holdings
        updated_count, inserted_count, deleted_count = await svc.upsert_user_holdings(
            holdings_list=holdings_list,
            user_id=UUID(user["user_id"]),
            user_broker_id=user_broker_id,
        )

        logger.info(
            "bulk_holdings_update_success",
            extra={
                "user_id": str(user["user_id"]),
                "user_broker_id": str(user_broker_id),
                "updated_count": updated_count,
                "inserted_count": inserted_count,
                "deleted_count": deleted_count,
            },
        )

        total_processed = updated_count + inserted_count
        message = f"Successfully processed {total_processed} holdings (updated: {updated_count}, inserted: {inserted_count}, deleted: {deleted_count})"
        if discrepancies:
            symbols_list = ", ".join(discrepancies.keys())
            message += f". Note: Some symbols had issues - {symbols_list}"

        return BulkHoldingsUploadResponse(
            success=True,
            records_processed=total_processed,
            message=message,
        )

    except ValueError as e:
        logger.error(
            "file_parsing_error",
            extra={
                "user_id": str(user["user_id"]),
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "bulk_holdings_update_error",
            extra={
                "user_id": str(user["user_id"]),
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {str(e)}",
        )
