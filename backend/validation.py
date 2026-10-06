"""Form validation for every form on the site: create account, login, and checkout.

Each rule is a plain function that returns the cleaned value or raises ValueError with a message
written for shoppers. The same rules are used two ways:
  * inside the Pydantic request models (auth.py, shop.py), so the API rejects bad data, and
  * by POST /api/validate/{form}, which the website calls as a shopper leaves each field, so
    mistakes show up next to the field before they press the button.

Validation errors come back as {"detail": "<first message>", "errors": {"<field>": "<message>"}}.
"""

import re
from datetime import date

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

NAME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '\-.][A-Za-zÀ-ÖØ-öø-ÿ]+)*\.?$")
CITY = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ '\-.][A-Za-zÀ-ÖØ-öø-ÿ]+)*$")
ZIP = re.compile(r"^\d{5}(?:-\d{4})?$")
ADDRESS = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9 .,'#/\-]+$")
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}
CARD_BRANDS = [  # (brand, pattern on the leading digits, allowed lengths, CVV length)
    ("American Express", re.compile(r"^3[47]"), {15}, 4),
    ("Visa", re.compile(r"^4"), {13, 16, 19}, 3),
    ("Mastercard", re.compile(r"^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))"), {16}, 3),
    ("Discover", re.compile(r"^(6011|65|64[4-9])"), {16, 19}, 3),
]


def _text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


# ---- People ------------------------------------------------------------------------

def check_name(value: str | None, label: str = "Name") -> str:
    v = _text(value)
    if not v:
        raise ValueError(f"{label} is required.")
    if len(v) > 50:
        raise ValueError(f"{label} must be 50 characters or fewer.")
    if not NAME.match(v):
        raise ValueError(f"{label} can only contain letters, spaces, hyphens, and apostrophes.")
    return v


def check_full_name(value: str | None, label: str = "Full name") -> str:
    v = _text(value)
    if not v:
        raise ValueError(f"{label} is required.")
    if len(v) > 80:
        raise ValueError(f"{label} must be 80 characters or fewer.")
    if not NAME.match(v):
        raise ValueError(f"{label} can only contain letters, spaces, hyphens, and apostrophes.")
    if " " not in v:
        raise ValueError("Please enter both a first and last name.")
    return v


def check_email(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("Email is required.")
    if " " in v:
        raise ValueError("Email can't contain spaces.")
    if "@" not in v:
        raise ValueError("Email needs an @, like you@yale.edu.")
    try:
        return validate_email(v, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise ValueError("Please enter a valid email address, like you@yale.edu.") from None


def check_password(value: str | None) -> str:
    v = value or ""
    if not v:
        raise ValueError("Password is required.")
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(v) > 128:
        raise ValueError("Password must be 128 characters or fewer.")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password needs at least one letter and one number.")
    return v


def check_phone(value: str | None) -> str:
    """US phone numbers: 10 digits (a leading 1 is allowed). Returned as (203) 555-0123."""
    v = _text(value)
    if not v:
        raise ValueError("Phone number is required.")
    if re.search(r"[^\d\s().+\-]", v):
        raise ValueError("Phone number can only contain digits, spaces, ( ), -, and +.")
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Phone number must have 10 digits, like (203) 555-0123.")
    if digits[0] in "01" or digits[3] in "01":
        raise ValueError("That isn't a valid US phone number (area code and exchange can't start with 0 or 1).")
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


# ---- Shipping address ----------------------------------------------------------------

def check_address(value: str | None) -> str:
    v = _text(value)
    if not v:
        raise ValueError("Street address is required.")
    if len(v) < 5 or len(v) > 100:
        raise ValueError("Street address must be 5 to 100 characters.")
    if not ADDRESS.match(v):
        raise ValueError("Please enter a street address with a number and street name, like 149 Elm St.")
    return v


def check_address2(value: str | None) -> str:
    v = _text(value)
    if len(v) > 60:
        raise ValueError("Apartment / suite must be 60 characters or fewer.")
    if v and not re.match(r"^[A-Za-z0-9 .,'#/\-]+$", v):
        raise ValueError("Apartment / suite has characters we can't ship to.")
    return v


def check_city(value: str | None) -> str:
    v = _text(value)
    if not v:
        raise ValueError("City is required.")
    if len(v) > 60 or not CITY.match(v):
        raise ValueError("Please enter a valid city name (letters only).")
    return v


def check_state(value: str | None) -> str:
    v = _text(value).upper()
    if not v:
        raise ValueError("State is required.")
    if v not in US_STATES:
        raise ValueError("Please use a 2-letter US state code, like CT.")
    return v


def check_zip(value: str | None) -> str:
    v = _text(value)
    if not v:
        raise ValueError("ZIP code is required.")
    if not ZIP.match(v):
        raise ValueError("ZIP code must be 5 digits (or ZIP+4, like 06511-1234).")
    return v


# ---- Payment -------------------------------------------------------------------------

def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def card_brand(digits: str) -> tuple[str, set[int], int] | None:
    for brand, pattern, lengths, cvv_len in CARD_BRANDS:
        if pattern.match(digits):
            return brand, lengths, cvv_len
    return None


def check_card_number(value: str | None) -> str:
    """Returns the digits only. We check the format; no card is ever charged."""
    v = (value or "").strip()
    if not v:
        raise ValueError("Card number is required.")
    if re.search(r"[^\d \-]", v):
        raise ValueError("Card number can only contain digits.")
    digits = re.sub(r"\D", "", v)
    found = card_brand(digits)
    if found is None:
        raise ValueError("We accept Visa, Mastercard, American Express, and Discover.")
    brand, lengths, _ = found
    if len(digits) not in lengths:
        raise ValueError(f"{brand} numbers are {' or '.join(str(n) for n in sorted(lengths))} digits.")
    if not luhn_ok(digits):
        raise ValueError("That card number isn't valid. Please check for typos.")
    return digits


def check_expiry(value: str | None, today: date | None = None) -> str:
    v = (value or "").strip().replace(" ", "")
    if not v:
        raise ValueError("Expiration date is required.")
    m = re.match(r"^(\d{1,2})/(\d{2}|\d{4})$", v)
    if not m:
        raise ValueError("Use MM/YY for the expiration date, like 08/28.")
    month, year = int(m.group(1)), int(m.group(2))
    year = year + 2000 if year < 100 else year
    if not 1 <= month <= 12:
        raise ValueError("Expiration month must be 01 to 12.")
    today = today or date.today()
    if (year, month) < (today.year, today.month):
        raise ValueError("This card has expired.")
    if year > today.year + 20:
        raise ValueError("That expiration year is too far in the future.")
    return f"{month:02d}/{year % 100:02d}"


def check_cvv(value: str | None, card_number: str | None = None) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError("Security code (CVV) is required.")
    if not v.isdigit():
        raise ValueError("Security code can only contain digits.")
    digits = re.sub(r"\D", "", card_number or "")
    found = card_brand(digits) if digits else None
    expected = found[2] if found else None
    if expected and len(v) != expected:
        raise ValueError(f"The security code for {found[0]} is {expected} digits.")
    if not expected and len(v) not in (3, 4):
        raise ValueError("Security code must be 3 or 4 digits.")
    return v


# ---- Live validation endpoint --------------------------------------------------------
# Field names match the JSON the website sends for each form.

FORMS = {
    "signup": {
        "first_name": lambda d: check_name(d.get("first_name"), "First name"),
        "last_name": lambda d: check_name(d.get("last_name"), "Last name"),
        "email": lambda d: check_email(d.get("email")),
        "password": lambda d: check_password(d.get("password")),
        "confirm_password": lambda d: _matches(d),
    },
    "login": {
        "email": lambda d: check_email(d.get("email")),
    },
    "checkout": {
        "full_name": lambda d: check_full_name(d.get("full_name")),
        "email": lambda d: check_email(d.get("email")),
        "phone": lambda d: check_phone(d.get("phone")),
        "address1": lambda d: check_address(d.get("address1")),
        "address2": lambda d: check_address2(d.get("address2")),
        "city": lambda d: check_city(d.get("city")),
        "state": lambda d: check_state(d.get("state")),
        "zip": lambda d: check_zip(d.get("zip")),
        "card_name": lambda d: check_full_name(d.get("card_name"), "Name on card"),
        "card_number": lambda d: check_card_number(d.get("card_number")),
        "expiry": lambda d: check_expiry(d.get("expiry")),
        "cvv": lambda d: check_cvv(d.get("cvv"), d.get("card_number")),
    },
}


def _matches(d: dict) -> str:
    if not d.get("confirm_password"):
        raise ValueError("Please confirm your password.")
    if d.get("confirm_password") != d.get("password"):
        raise ValueError("Passwords don't match.")
    return d["confirm_password"]


def validate_form(form: str, data: dict, fields: list[str] | None = None) -> dict:
    """Check the given fields (or all of them). Returns {"valid", "errors", "cleaned"}."""
    rules = FORMS[form]
    errors: dict[str, str] = {}
    cleaned: dict[str, str] = {}
    for name in fields or list(rules):
        if name not in rules:
            continue
        try:
            cleaned[name] = rules[name](data)
        except ValueError as e:
            errors[name] = str(e)
    # Never echo card numbers, security codes, or passwords back; a valid card only reveals its brand.
    if "card_number" in cleaned:
        cleaned["card_brand"] = card_brand(cleaned["card_number"])[0]
    for secret in ("card_number", "cvv", "password", "confirm_password"):
        cleaned.pop(secret, None)
    return {"valid": not errors, "errors": errors, "cleaned": cleaned}


router = APIRouter(prefix="/api/validate", tags=["validation"])


@router.post("/{form}")
async def validate(form: str, request: Request):
    """Live check for one or more fields: body is the form's fields, optional ?fields=a,b."""
    if form not in FORMS:
        return JSONResponse({"detail": "Unknown form."}, status_code=404)
    try:
        data = await request.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data = {k: (v if isinstance(v, str) else "") for k, v in data.items()}
    raw_fields = request.query_params.get("fields")
    fields = [f for f in raw_fields.split(",") if f] if raw_fields else None
    return validate_form(form, data, fields)


# ---- Friendlier validation errors for the whole API ------------------------------------

async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn Pydantic's error list into {"detail": first message, "errors": {field: message}}."""
    errors: dict[str, str] = {}
    for err in exc.errors():
        field = str(err["loc"][-1]) if err.get("loc") else "form"
        msg = str(err.get("msg", "Invalid value.")).removeprefix("Value error, ")
        if err.get("type") == "missing":
            msg = "This field is required."
        errors.setdefault(field, msg)
    detail = next(iter(errors.values()), "Please check the form and try again.")
    return JSONResponse({"detail": detail, "errors": errors}, status_code=422)
