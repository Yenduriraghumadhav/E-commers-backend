from debaggingFile.loggerFile import logger
from fastapi import APIRouter , status ,Response , Cookie ,HTTPException
from dataBase.dataBaseConnectivity import db

router = APIRouter()
user_collection = db["usersDetails"]
loginInfo_collection = db["Userslogin_history"]


@router.post("/Userlogout")
async def UsersLogoutAPI(response: Response,jwt_Token: str | None = Cookie(default=None)):

    if not jwt_Token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User Jwt Token Not Found"
        )

    try:
        login_data = loginInfo_collection.find_one({
            "token": jwt_Token
        })

        if not login_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid User Jwt Token"
            )

        loginInfo_collection.delete_one({
            "token": jwt_Token
        })

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error checking login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong"
        )

    response.delete_cookie(key="jwt_Token")

    logger.info("User logged out successfully.")

    return {
        "message": "Logout successful"
    }


