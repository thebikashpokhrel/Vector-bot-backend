from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import base64
import json
import os
import logging
from google_auth_oauthlib.flow import InstalledAppFlow

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection string
MONGODB_URL = os.getenv("MONGODB_URL")

# Initialize FastAPI app
app = FastAPI()

# Connect to MongoDB
client = AsyncIOMotorClient(MONGODB_URL)
db = client["vector-bot"]
collection = db["classroom-tokens"]


# Root route
@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return HTMLResponse(
        content=f"<html><body><h1>Alive</h1></body></html>",
        status_code=200,
    )


# GET Route after the OAuth flow is completed
@app.get("/classroom/subscribe/")
async def create_user(request: Request):
    try:
        # Extract query parameters
        query_params = request.query_params
        code = query_params.get("code")
        state_encoded = query_params.get("state")

        if not code or not state_encoded:
            return JSONResponse(
                status_code=400, content={"error": "Missing code or state parameter"}
            )

        # Decode the state parameter to get user_id
        state_json = base64.urlsafe_b64decode(state_encoded.encode()).decode()
        state_data = json.loads(state_json)
        clientid = state_data.get("clientid")

        if not clientid:
            return JSONResponse(
                status_code=400, content={"error": "user_id not found in state"}
            )

        logger.info(f"Received user_id: {clientid}, code: {code}")

        user = await collection.find_one({"client_id": clientid})

        SCOPES = [
            "https://www.googleapis.com/auth/classroom.courses.readonly",
            "https://www.googleapis.com/auth/classroom.announcements",
            "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
        ]

        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",  # Path to credentials file
            scopes=SCOPES,
            redirect_uri="http://localhost:8001/classroom/subscribe",  # Redirect URI used during OAuth2 flow
        )

        flow.fetch_token(code=code)
        creds = flow.credentials

        user_dict = {"client_id": clientid, "token": creds.to_json()}
        # Insert the user data into MongoDB
        if not user:
            await collection.insert_one(user_dict)
        logger.info(f"Client Id {clientid} subscribed")

        return HTMLResponse(
            content=f"<html><body><h1>Subscription Successful</h1><p>User {clientid} has been successfully subscribed.</p></body></html>",
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Failed to insert user: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})


# GET route to get user data
@app.get("/classroom/check/")
async def get_token(clientid: str):
    try:
        user = await collection.find_one({"client_id": clientid})
        if user:
            logger.info(f"Token retrieved for user {clientid}")
            return JSONResponse(status_code=200, content={"token": user["token"]})
        return JSONResponse(status_code=404, content={"error": "User not found"})
    except Exception as e:
        logger.error(f"Failed to retrieve token: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})


# DELETE route to delete user data
@app.delete("/classroom/unsubscribe")
async def delete_user(clientid: str):
    try:
        result = await collection.delete_one({"client_id": clientid})
        if result.deleted_count == 1:
            logger.info(f"User {clientid} unsubscribed")
            return JSONResponse(
                status_code=200, content={"message": "User unsubscribed successfully"}
            )
        return JSONResponse(status_code=404, content={"error": "User not found"})
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
