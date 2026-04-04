from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class TelemetryClientInfo(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    appVersionName: str = Field(min_length=1)
    appVersionCode: StrictInt = Field(ge=0)
    sdkInt: StrictInt = Field(ge=0)
    device: str = Field(min_length=1)
    model: str = Field(min_length=1)


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: StrictInt = Field(ge=0)
    timestampMs: StrictInt = Field(ge=0)
    userId: str | None = Field(default=None, min_length=1)
    packageName: str = Field(min_length=1)
    playIntegrityVersionMajor: StrictInt | None = Field(default=None, ge=0)
    playIntegrityVersionMinor: StrictInt | None = Field(default=None, ge=0)
    playIntegrityVersionPatch: StrictInt | None = Field(default=None, ge=0)
    eventType: Literal["request", "response"]
    success: bool | None = None
    errorCode: StrictInt | None = None
    retriable: bool | None = None
    source: str = Field(min_length=1)
    attemptCount: StrictInt = Field(default=0, ge=0)


class TelemetryUploadRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    schemaVersion: StrictInt = Field(ge=1)
    batchId: str = Field(min_length=1)
    sentAtMs: StrictInt = Field(ge=0)
    events: list[TelemetryEvent] = Field(default_factory=list)


class TelemetryUploadResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    accepted: bool = False
    ackId: str | None = None
    retryable: bool = True
    retryAfterMs: StrictInt | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    databaseReady: bool
    databasePath: str


class ErrorResponse(BaseModel):
    accepted: bool = False
    retryable: bool = False
    error: str
