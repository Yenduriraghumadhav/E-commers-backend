from starlette import status
from fastapi import Cookie, HTTPException, status
from dataBase.dataBaseConnectivity import db
from schemas.vendoreJWTTokenSchema import VendoreJWTTokenRequest
from fastapi import APIRouter, HTTPException ,Response
from fastapi import Cookie
from debaggingFile.loggerFile import logger

router = APIRouter()
jwttoken_toaddProduct = db["VendoreJwtTokenFile"]

@router.post("/vendorelogout")
async def vendorelogout( response: Response,jwt_token: str | None = Cookie(default=None)):

    if not jwt_token:
        logger.error("JWT token not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token not provided"
        )

    try:
        verification = await jwttoken_toaddProduct.find_one({
            "token": jwt_token
        })

        if not verification:
            logger.error(
                f"Logout verification failed , for token "
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Verification failed"
            )

        logout = await jwttoken_toaddProduct.delete_one({
            "token": jwt_token
        })

        response.delete_cookie(key="jwt_token")

        logger.info(
            f"Vendor logout successful"
            f"deleted_login={logout.deleted_count}"
        )

        return {
            "message": "Logout successful"
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Vendor logout error | error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong"
        )

