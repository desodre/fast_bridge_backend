from pydantic import BaseModel, Field

class AdbResponse(BaseModel):
    device_serial:str = Field(description='device serial')
    stdout:str = Field(description='return of command')
    exit_code:int = Field(description='exit code of command, can be 0 or 1')