# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
import json
from datetime import datetime
from .timezone_utils import utc_to_iraq, format_iraq_datetime


class IraqTimezoneMiddleware(BaseHTTPMiddleware):
    """
    Middleware to convert all datetime values in JSON responses to Iraq timezone
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Only process JSON responses
        if response.headers.get("content-type", "").startswith("application/json"):
            # Skip if it's a streaming response
            if isinstance(response, StreamingResponse):
                return response
            
            try:
                # Get response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                
                # Parse JSON
                data = json.loads(body.decode())
                
                # Convert datetime fields
                converted_data = self._convert_datetimes(data)
                
                # Create new response with converted data
                new_body = json.dumps(converted_data, ensure_ascii=False, default=str).encode()
                
                return Response(
                    content=new_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type="application/json"
                )
            except Exception:
                # If conversion fails, return original response
                return response
        
        return response
    
    def _convert_datetimes(self, data):
        """
        Recursively convert datetime strings to Iraq timezone
        """
        if isinstance(data, dict):
            return {key: self._convert_datetimes(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._convert_datetimes(item) for item in data]
        elif isinstance(data, str):
            # Try to parse as datetime
            return self._try_convert_datetime_string(data)
        else:
            return data
    
    def _try_convert_datetime_string(self, value: str):
        """
        Try to parse and convert datetime string to Iraq timezone
        """
        # Common datetime formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
            "%Y-%m-%dT%H:%M:%S",      # ISO format
            "%Y-%m-%d %H:%M:%S.%f",   # Space separated with microseconds
            "%Y-%m-%d %H:%M:%S",      # Space separated
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                # Convert to Iraq timezone and format
                iraq_dt = utc_to_iraq(dt)
                # Return in ISO format
                return iraq_dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        
        # Not a datetime string, return as is
        return value
