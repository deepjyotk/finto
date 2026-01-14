"""Holdings API endpoints - depends ONLY on service layer"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.api.schemas.holdings import (
    BulkHoldingsUploadResponse,
    DeleteBrokerHoldingsResponse,
    SyncHoldingsRequest,
    SyncHoldingsResponse,
    SyncStatusResponse,
)
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
    password: Annotated[
        str | None, Form(description="Optional password for password-protected Excel files")
    ] = None,
) -> BulkHoldingsUploadResponse:
    """
    Upload and process equity holdings from Excel or CSV file.

    Accepts files in the following formats:
    - Excel (.xlsx, .xls) - supports password-protected files if password is provided
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

    **Password protection**: If your Excel file is password-protected, provide
    the password in the 'password' form field.

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
            file_content=file_content,
            filename=file.filename,
            broker_id=broker_id,
            password=password,
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
    password: Annotated[
        str | None, Form(description="Optional password for password-protected Excel files")
    ] = None,
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
            file_content=file_content,
            filename=file.filename,
            broker_id=metadata.broker_id,
            password=password,
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


@router.post(
    "/sync",
    response_model=SyncHoldingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync holdings from Kite to database",
    description="Sync holdings from Kite Connect API. For each holding, checks if it exists by symbol and updates if changed, or creates new.",
    responses={
        200: {"description": "Holdings successfully synced"},
        400: {"description": "Invalid request data"},
        401: {"description": "Not authenticated or invalid token"},
    },
)
async def sync_holdings(
    request: SyncHoldingsRequest,
    svc: Annotated[HoldingsService, Depends(get_holdings_service)],
    broker_svc: Annotated[BrokerService, Depends(get_broker_service)],
    user: dict = Depends(require_auth),
) -> SyncHoldingsResponse:
    """
    Sync holdings from Kite Connect to database.

    For each holding in the request:
    - Check if it exists for the user by symbol
    - If exists and changed, update it
    - If not exists, create new
    - Track sync in holding_syncs table
    """
    user_id = UUID(user["user_id"])

    logger.info(
        "holdings_sync_attempt",
        extra={
            "user_id": str(user_id),
            "broker_name": request.broker_name,
            "holdings_count": len(request.holdings),
        },
    )

    try:
        # Get broker_id by name from database
        brokers = await broker_svc.get_all_brokers()
        matched_broker = next(
            (b for b in brokers if b.get("broker_name", "").lower() == request.broker_name.lower()),
            None,
        )
        if matched_broker is None:
            available_brokers = [b["broker_name"] for b in brokers]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Broker '{request.broker_name}' not found in database. Available brokers: {available_brokers}",
            )
        broker_id = UUID(matched_broker["broker_id"])

        # Convert Pydantic models to dicts
        holdings_list = [holding.model_dump() for holding in request.holdings]

        # Sync holdings
        synced_count, updated_count = await svc.sync_holdings(
            holdings_list=holdings_list,
            user_id=user_id,
            broker_id=broker_id,
        )

        logger.info(
            "holdings_sync_success",
            extra={
                "user_id": str(user_id),
                "synced_count": synced_count,
                "updated_count": updated_count,
            },
        )

        message = f"Successfully synced {synced_count} holdings, updated {updated_count}"
        return SyncHoldingsResponse(
            synced_count=synced_count,
            updated_count=updated_count,
            message=message,
        )

    except Exception as e:
        logger.error(
            "holdings_sync_error",
            extra={
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync holdings: {str(e)}",
        )


@router.get(
    "/sync-status",
    response_model=SyncStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get most recent sync status",
    description="Get the most recent holdings sync record for the authenticated user",
    responses={
        200: {"description": "Sync status retrieved successfully"},
        401: {"description": "Not authenticated or invalid token"},
    },
)
async def get_sync_status(
    svc: Annotated[HoldingsService, Depends(get_holdings_service)],
    user: dict = Depends(require_auth),
) -> SyncStatusResponse:
    """
    Get the most recent sync status for the authenticated user.

    Returns the timestamp, synced count, and updated count from the last sync operation.
    """
    user_id = UUID(user["user_id"])

    logger.info(
        "sync_status_request",
        extra={
            "user_id": str(user_id),
        },
    )

    try:
        sync_status = await svc.get_sync_status(user_id)

        if sync_status is None:
            return SyncStatusResponse(
                last_sync=None,
                synced_count=None,
                updated_count=None,
            )

        logger.info(
            "sync_status_retrieved",
            extra={
                "user_id": str(user_id),
                "last_sync": sync_status["last_sync"],
            },
        )

        return SyncStatusResponse(
            last_sync=sync_status["last_sync"],
            synced_count=sync_status["synced_count"],
            updated_count=sync_status["updated_count"],
        )

    except Exception as e:
        logger.error(
            "sync_status_error",
            extra={
                "user_id": str(user_id),
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}",
        )


@router.delete(
    "/broker/{user_broker_id}",
    response_model=DeleteBrokerHoldingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete broker holdings for user",
    description="Delete all holdings and metadata for a specific broker using user_broker_id (metadata primary key)",
    responses={
        200: {"description": "Holdings and metadata successfully deleted (or already deleted - idempotent)"},
        401: {"description": "Not authenticated or invalid token"},
        404: {"description": "Holdings metadata not found or access denied"},
    },
)
async def delete_broker_holdings(
    user_broker_id: UUID,
    svc: Annotated[HoldingsService, Depends(get_holdings_service)],
    user: dict = Depends(require_auth),
) -> DeleteBrokerHoldingsResponse:
    """
    Delete all holdings and metadata for a specific broker using user_broker_id.

    This endpoint:
    - Deletes all equity holdings associated with the user-broker pair
    - Deletes the metadata record for the user-broker pair
    - Returns the count of deleted holdings

    **Authentication required**: Yes (JWT token in cookie)

    Args:
        user_broker_id: UUID of the user-broker metadata (primary key from equity_holdings_in_metadata)
        svc: HoldingsService instance
        user: Authenticated user info from JWT token

    Returns:
        DeleteBrokerHoldingsResponse with deletion details
    """
    user_id = UUID(user["user_id"])

    logger.info(
        "delete_broker_holdings_attempt",
        extra={
            "user_id": str(user_id),
            "user_broker_id": str(user_broker_id),
        },
    )

    try:
        # Verify metadata exists and belongs to user
        metadata = await svc.repo.get_metadata_by_user_broker_id(user_broker_id, user_id)
        if metadata is None:
            logger.info(
                "delete_broker_holdings_not_found",
                extra={
                    "user_id": str(user_id),
                    "user_broker_id": str(user_broker_id),
                },
            )
            message = f"No holdings or metadata found for user_broker_id {user_broker_id} (already deleted or never existed)"
            return DeleteBrokerHoldingsResponse(
                success=True,
                deleted_holdings_count=0,
                metadata_deleted=False,
                message=message,
            )

        # Count holdings before deletion
        holdings = await svc.repo.by_user_broker_id(user_broker_id)
        deleted_holdings_count = len(holdings)

        # Explicitly delete holdings first (from equity_holdings_in table)
        deleted_holdings = await svc.repo.delete_by_user_broker_id(user_broker_id)
        
        # Then delete metadata record (from equity_holdings_in_metadata table)
        from sqlalchemy import delete
        from src.models.equity_holding_metadata import EquityHoldingMetadata
        
        await svc.repo.session.execute(
            delete(EquityHoldingMetadata).where(
                EquityHoldingMetadata.user_broker_id == user_broker_id
            )
        )
        
        # Commit at the use-case boundary
        await svc.repo.session.commit()

        logger.info(
            "delete_broker_holdings_success",
            extra={
                "user_id": str(user_id),
                "user_broker_id": str(user_broker_id),
                "deleted_holdings_count": deleted_holdings_count,
                "metadata_deleted": True,
            },
        )

        message = f"Successfully deleted {deleted_holdings_count} holdings and metadata for user_broker_id {user_broker_id}"

        return DeleteBrokerHoldingsResponse(
            success=True,
            deleted_holdings_count=deleted_holdings_count,
            metadata_deleted=True,
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "delete_broker_holdings_error",
            extra={
                "user_id": str(user_id),
                "user_broker_id": str(user_broker_id),
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete broker holdings: {str(e)}",
        )
