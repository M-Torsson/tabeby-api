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
        
        if response.headers.get("content-type", "").startswith("application/json"):
            if isinstance(response, StreamingResponse):
                return response
            
            try:
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                
                data = json.loads(body.decode())
                
                converted_data = self._convert_datetimes(data)
                
                new_body = json.dumps(converted_data, ensure_ascii=False, default=str).encode()
                
                return Response(
                    content=new_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type="application/json"
                )
            except Exception:
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
            return self._try_convert_datetime_string(data)
        else:
            return data
    
    def _try_convert_datetime_string(self, value: str):
        """
        Try to parse and convert datetime string to Iraq timezone
        """
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
            "%Y-%m-%dT%H:%M:%S",      # ISO format
            "%Y-%m-%d %H:%M:%S.%f",   # Space separated with microseconds
            "%Y-%m-%d %H:%M:%S",      # Space separated
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                iraq_dt = utc_to_iraq(dt)
                return iraq_dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        
        return value
