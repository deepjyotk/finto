"""Holdings API endpoints - depends ONLY on service layer"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.api.schemas.holdings import (
    BulkHoldingsUploadResponse,
    HoldingsRequestSchema,
    HoldingsResponseSchema,
)
from src.core.json_logging import logger_for
from src.core.middleware import require_auth
from src.dependencies import get_holdings_service
from src.services.holdings import HoldingsService
from src.utils.file_parser import parse_holdings_file

logger = logger_for(__name__)

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.post(
    "",
    response_model=HoldingsResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new equity holding",
    description="Save equity holding information for the authenticated user.",
    responses={
        201: {"description": "Holding successfully created"},
        401: {"description": "Not authenticated or invalid token"},
    },
)
async def create_holding(
    holding: HoldingsRequestSchema,
    svc: Annotated[HoldingsService, Depends(get_holdings_service)],
    user: dict = Depends(require_auth),
) -> HoldingsResponseSchema:
    """
    Create a new equity holding for the authenticated user.

    Saves equity holding information including:
    - Broker details
    - Symbol and ISIN
    - Quantities (available, long-term, pledged, etc.)
    - Prices and P&L information

    **Authentication required**: Yes (JWT token in cookie)

    Returns the created holding information.
    """
    logger.info(
        "create_holding_attempt",
        extra={
            "user_id": str(user["user_id"]),
            "broker_id": str(holding.broker_id),
            "symbol": holding.symbol,
        },
    )

    result = await svc.save_user_holding(holding_schema=holding, user_id=user["user_id"])

    logger.info(
        "create_holding_success",
        extra={
            "user_id": str(user["user_id"]),
            "holding_id": str(result.id),
            "symbol": result.symbol,
        },
    )

    return result


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
    - Quantity Discrepant
    - Quantity Long Term
    - Quantity Pledged (Margin)
    - Quantity Pledged (Loan)
    - Average Price
    - Previous Closing Price
    - Unrealized P&L
    - Unrealized P&L Pct.

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

        # Parse file to holdings list
        holdings_list = parse_holdings_file(
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

        return BulkHoldingsUploadResponse(
            success=True,
            records_processed=records_processed,
            message=f"Successfully uploaded {records_processed} holdings",
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
