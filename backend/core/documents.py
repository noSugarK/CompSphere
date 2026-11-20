import hashlib
import hmac
import re

from django.conf import settings

from core.exceptions import BusinessError

DOCUMENT_TYPES = ("id_card", "passport")
ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
ID_CHECK = "10X98765432"
# 05 §登录: 规范化 = 去首尾空格、字母大写并保留前导零；身份证固定 18 位含校验位。
ID_PATTERN = re.compile(r"\A\d{17}[\dX]\Z")
PASSPORT_PATTERN = re.compile(r"\A[A-Z0-9]{5,12}\Z")
COUNTRY_PATTERN = re.compile(r"\A[A-Z]{2}\Z")


def normalize(document_type, country, number):
    doc_type = (document_type or "").strip().lower()
    region = (country or "").strip().upper()
    value = (number or "").strip().upper()
    if doc_type not in DOCUMENT_TYPES:
        raise BusinessError(42206, "Document type is not supported", 422)
    if not COUNTRY_PATTERN.match(region):
        raise BusinessError(42206, "Issuing country is invalid", 422)
    if doc_type == "id_card":
        if region != "CN":
            raise BusinessError(42206, "ID card must use CN", 422)
        if not ID_PATTERN.match(value):
            raise BusinessError(42206, "ID card number format is invalid", 422)
        total = sum(int(value[i]) * ID_WEIGHTS[i] for i in range(17))
        if ID_CHECK[total % 11] != value[17]:
            raise BusinessError(42206, "ID card check digit is invalid", 422)
    elif not PASSPORT_PATTERN.match(value):
        # 05: 护照按签发国校验；首期仅长度/字符集规则，格式正确不代表实名核验。
        raise BusinessError(42206, "Passport number format is invalid", 422)
    return doc_type, region, value


def digest(document_type, country, number):
    return hmac.new(
        settings.DOC_HASH_PEPPER.encode(),
        f"{document_type}|{country}|{number}".encode(),
        hashlib.sha256,
    ).hexdigest()


def bind(document_type, country, number):
    """Validate, hash and reduce to the storable fields; the full number never
    leaves the caller. Returns (type, country, normalized, hash, last4)."""
    doc_type, region, value = normalize(document_type, country, number)
    return doc_type, region, value, digest(doc_type, region, value), value[-4:]
