from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.engines.scoring_engine import DEFAULT_WEIGHTS


class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)


class DemoLogin(BaseModel):
    role: Literal['PROCUREMENT_OFFICER', 'AUDITOR', 'ADMIN']


class DecisionRequest(BaseModel):
    run_id: str
    decision: Literal['QUALIFIED', 'DISQUALIFIED', 'NEEDS CLARIFICATION']
    reason: str = Field(min_length=5, max_length=4000)
    comments: str = Field(default='', max_length=4000)

    @field_validator('reason')
    @classmethod
    def reason_required(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('Give a substantive reason for the officer decision')
        return value.strip()


class TenderRequest(BaseModel):
    reference: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=5, max_length=255)
    department: str = Field(default='Chennai Petroleum Corporation Limited', max_length=255)
    deadline: str
    description: str = Field(default='', max_length=8000)
    required_documents: list[str] = Field(default=['pan', 'gst_certificate', 'udyam', 'oem_authorization', 'experience_certificate', 'tax_compliance'], min_length=1, max_length=15)
    local_content_threshold: float = Field(default=50, ge=0, le=100)

    @field_validator('deadline')
    @classmethod
    def valid_deadline(cls, value):
        from datetime import datetime
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value


class BidRequest(BaseModel):
    tender_id: str
    name: str = Field(min_length=3, max_length=255)
    pan: str = Field(pattern=r'^[A-Z]{5}\d{4}[A-Z]$')
    gstin: str = Field(pattern=r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')
    udyam: str = Field(default='', max_length=30)
    address: str = Field(default='', max_length=1000)


class RuleRequest(BaseModel):
    id: str
    rule_id: str
    name: str = Field(min_length=3, max_length=255)
    category: str = Field(max_length=40)
    expression: dict
    severity: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    required: bool
    enabled: bool

    @field_validator('expression')
    @classmethod
    def validate_expression(cls, value):
        from app.engines.rule_engine import ALLOWED_OPERATORS
        if value.get('op') not in ALLOWED_OPERATORS:
            raise ValueError('Unknown rule operator')
        if value['op'] == 'source_status' and value.get('source') not in {
            'PAN', 'GST', 'UDYAM', 'BLACKLIST', 'OEM', 'INCOME_TAX', 'EPFO', 'ESIC', 'STARTUP_INDIA', 'NSIC', 'DIGILOCKER'}:
            raise ValueError('Unknown source')
        if value['op'] == 'document_present' and value.get('document') not in {
            'pan', 'gst_certificate', 'udyam', 'incorporation', 'oem_authorization', 'experience_certificate', 'bank_certificate', 'tax_compliance'}:
            raise ValueError('Unknown document classification')
        if value['op'] == 'minimum_field' and (value.get('field') != 'local_content' or
                not isinstance(value.get('value'), (float, int)) or not 0 <= value['value'] <= 100):
            raise ValueError('Local content threshold must be between 0 and 100')
        return value


class RulesUpdate(BaseModel):
    rules: list[RuleRequest] = Field(min_length=1, max_length=50)
    scoring_weights: dict[str, float]

    @field_validator('scoring_weights')
    @classmethod
    def weights_total(cls, value):
        if set(value) != set(DEFAULT_WEIGHTS) or any(v < 0 or v > 100 for v in value.values()) or abs(sum(value.values())-100) > .001:
            raise ValueError('The six scoring components must have non-negative weights totaling 100')
        return value


class ProcessRequest(BaseModel):
    unavailable_sources: list[str] = Field(default=[], max_length=11)
