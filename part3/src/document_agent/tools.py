from __future__ import annotations

import ast
from datetime import date, datetime, timedelta
from decimal import Decimal, DivisionByZero, InvalidOperation
import json
import operator
import os
import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool


MAX_EXPRESSION_LENGTH = 200
MAX_AST_NODES = 50
MAX_ABSOLUTE_RESULT = Decimal("1000000000000000")
MAX_DATE_OFFSET_DAYS = 3_650
ALLOWED_EXPRESSION = re.compile(r"^[0-9+\-*/().%\s]+$")
ALLOWED_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}
ALLOWED_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class ToolInputError(ValueError):
    """Raised when an agent tool receives unsafe or incomplete arguments."""


def calculate_expression(expression: str) -> str:
    normalized = re.sub(r"\s+", " ", expression).strip()
    if not normalized:
        raise ToolInputError("Calculator expression cannot be empty.")
    if len(normalized) > MAX_EXPRESSION_LENGTH:
        raise ToolInputError(
            f"Calculator expression cannot exceed "
            f"{MAX_EXPRESSION_LENGTH} characters."
        )
    if not ALLOWED_EXPRESSION.fullmatch(normalized):
        raise ToolInputError(
            "Calculator accepts only numbers, parentheses, and "
            "+, -, *, /, or % operators."
        )

    try:
        parsed = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise ToolInputError("Calculator expression is invalid.") from exc
    if sum(1 for _ in ast.walk(parsed)) > MAX_AST_NODES:
        raise ToolInputError("Calculator expression is too complex.")

    try:
        result = _evaluate_node(parsed.body)
    except (DivisionByZero, ZeroDivisionError) as exc:
        raise ToolInputError("Calculator cannot divide by zero.") from exc
    except (InvalidOperation, OverflowError) as exc:
        raise ToolInputError("Calculator could not evaluate the expression.") from exc
    if not result.is_finite() or abs(result) > MAX_ABSOLUTE_RESULT:
        raise ToolInputError("Calculator result is outside the allowed range.")
    return _format_decimal(result)


def calculate_date(
    operation: Literal["today", "add_days", "days_between"],
    *,
    start_date: str | None = None,
    days: int | None = None,
    end_date: str | None = None,
    timezone_name: str = "Asia/Singapore",
    current_date: date | None = None,
) -> str:
    if operation == "today":
        if any(value is not None for value in (start_date, days, end_date)):
            raise ToolInputError(
                "The today operation does not accept date arguments."
            )
        if current_date is not None:
            return current_date.isoformat()
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ToolInputError(
                f"Unknown timezone: {timezone_name}"
            ) from exc
        return datetime.now(timezone).date().isoformat()

    parsed_start = _parse_iso_date(start_date, "start_date")
    if operation == "add_days":
        if days is None or isinstance(days, bool):
            raise ToolInputError(
                "The add_days operation requires an integer days value."
            )
        if end_date is not None:
            raise ToolInputError(
                "The add_days operation does not accept end_date."
            )
        if abs(days) > MAX_DATE_OFFSET_DAYS:
            raise ToolInputError(
                f"Date offset cannot exceed {MAX_DATE_OFFSET_DAYS} days."
            )
        return (parsed_start + timedelta(days=days)).isoformat()

    if operation == "days_between":
        if days is not None:
            raise ToolInputError(
                "The days_between operation does not accept days."
            )
        parsed_end = _parse_iso_date(end_date, "end_date")
        return str((parsed_end - parsed_start).days)

    raise ToolInputError(
        "Date operation must be today, add_days, or days_between."
    )


@tool
def calculator(expression: str) -> str:
    """Evaluate necessary expense arithmetic.

    Use this only when the user asks for a calculation. Do not use it
    for a direct policy lookup. The expression may contain numbers,
    parentheses, addition, subtraction, multiplication, division, or
    modulo.
    """

    try:
        result = calculate_expression(expression)
        return json.dumps(
            {
                "status": "ok",
                "expression": expression,
                "result": result,
            },
            sort_keys=True,
        )
    except ToolInputError as exc:
        return json.dumps(
            {"status": "error", "error": str(exc)},
            sort_keys=True,
        )


@tool
def date_tool(
    operation: Literal["today", "add_days", "days_between"],
    start_date: str | None = None,
    days: int | None = None,
    end_date: str | None = None,
) -> str:
    """Get today's date or perform necessary calendar-date arithmetic.

    Use today with no other arguments. Use add_days with start_date and
    days. Use days_between with start_date and end_date. Dates must use
    YYYY-MM-DD. Ask the user for missing dates instead of inventing them.
    """

    timezone_name = os.environ.get(
        "PART3_TIMEZONE",
        "Asia/Singapore",
    ).strip() or "Asia/Singapore"
    try:
        result = calculate_date(
            operation,
            start_date=start_date,
            days=days,
            end_date=end_date,
            timezone_name=timezone_name,
        )
        return json.dumps(
            {
                "status": "ok",
                "operation": operation,
                "result": result,
                "timezone": timezone_name,
            },
            sort_keys=True,
        )
    except ToolInputError as exc:
        return json.dumps(
            {"status": "error", "error": str(exc)},
            sort_keys=True,
        )


def _evaluate_node(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(
            node.value,
            (int, float),
        ):
            raise ToolInputError("Calculator accepts numeric values only.")
        return Decimal(str(node.value))
    if isinstance(node, ast.BinOp):
        operation = ALLOWED_BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ToolInputError("Calculator operator is not allowed.")
        return operation(
            _evaluate_node(node.left),
            _evaluate_node(node.right),
        )
    if isinstance(node, ast.UnaryOp):
        operation = ALLOWED_UNARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise ToolInputError("Calculator operator is not allowed.")
        return operation(_evaluate_node(node.operand))
    raise ToolInputError("Calculator expression contains unsupported syntax.")


def _parse_iso_date(value: str | None, field_name: str) -> date:
    if not value:
        raise ToolInputError(f"{field_name} is required.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolInputError(
            f"{field_name} must use YYYY-MM-DD."
        ) from exc


def _format_decimal(value: Decimal) -> str:
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"
