from dotenv import load_dotenv
from fastapi import FastAPI , Request
load_dotenv()
from debaggingFile.loggerFile import logger
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apis.totalpersonalDetailsAPIS.users_personalDetailsAPIS import router as users_personalDetailsAPI
from apis.totalLoginAPIS.usersLogin import router as users_loginAPI
from apis.totalpersonalDetailsAPIS.vendors__personalDetailsAPIS import router as vendors__personalDetailsAPI
from apis.totalLoginAPIS.vendorsLogin import router as vendors_LoginAPI
from apis.ForgotPasswordAPIS.usersforgotPasswordAPIs import router as users_forgotPasswordAPIs
from apis.ForgotPasswordAPIS.VendoresForgotPassword import router as  vendoreForgotPassword
from apis.LogoutAPIS.VendoreLogoutAPIS import router as vendorelogout
from apis.vendoreProductAPI import router as vendoreProductAPI
from apis.TemporareUserAPI import router as authInticationAPI
from apis.UsersADDTOCARTAPI import router as UsersADDTOCARTAPI
from apis.UsersWishListAPI import router as UsersWishListAPI
from apis.LogoutAPIS.userLogoutAPIS import router as logoutAPI
from apis.userOrdersAPIS.userOrdersAPI import router as ordersAPI
from apis.ProductsAPI import router as productsAPI
from apis.OrderTrackingAPIS.orderTrackingAPI import router as orderTrackingAPI
from apis.VendoreAPIS import router as vendoreAPI


app = FastAPI()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request,exc: Exception):

    logger.exception(
        f"Unhandled exception | "
        f"{request.method} {request.url}"
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error"
        }
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(users_personalDetailsAPI)
app.include_router(vendors__personalDetailsAPI)
app.include_router(users_loginAPI)
app.include_router(vendors_LoginAPI)
app.include_router(users_forgotPasswordAPIs)
app.include_router(vendoreForgotPassword)
app.include_router(vendoreProductAPI)
app.include_router(authInticationAPI)
app.include_router(UsersADDTOCARTAPI)
app.include_router(UsersWishListAPI)
app.include_router(vendorelogout)
app.include_router(logoutAPI)
app.include_router(ordersAPI)
app.include_router(productsAPI)
app.include_router(orderTrackingAPI)
app.include_router(vendoreAPI)


