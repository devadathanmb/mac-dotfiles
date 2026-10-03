# Comment Examples

Use this file when the main skill is not enough to judge a comment or when several comments need a consistent shape.

## Repeating Code

```python
# Bad
# Set the user name.
user.name = name

# Good
# Vendor exports can send blank display names; keep the existing name in that case.
if name:
    user.name = name
```

## Naming The Helper

```python
# Bad
# Call _merge_composite_params to merge params.
query_object["params"] = self._merge_composite_params(param_groups=partial_params)

# Good
# Keep boolean groups nested so every filter condition still applies.
query_object["params"] = self._merge_composite_params(param_groups=partial_params)
```

## Summary Comment for Complex Data Flow

```python
# Bad
# Loop through params and append composite params.
for param_group in param_groups:
    ...

# Good
# Boolean operators describe how filters relate; they are not record fields.
for param_group in param_groups:
    ...
```

## Failed Obvious Approach

```python
# Bad
# Handle nulls.
if op == InOperator.NOT_IN:
    ...

# Good
# SQL treats NULL NOT IN (...) as NULL, not TRUE. Project and category NOT_IN
# filters should include rows where the field is NULL.
if op == InOperator.NOT_IN:
    ...
```

## Bad Name vs Comment

```python
# Bad
def clean_reply(request: Request, reply: Reply) -> None:
    # Enforce limits on reply as stated in request.
    ...

# Better
def enforce_limits_from_request(request: Request, reply: Reply) -> None:
    ...
```

## Concrete Nouns

```python
# Bad
# Keep this out because callers handle it.

# Good
# `user_id` identifies the caller; the filter parser must not receive it.
```

```python
# Bad
# Insert payload into cache if it is not too big.

# Good
# Insert payload into cache if payload is under MAX_CACHE_BYTES.
```

## Do Not Translate The Whole Block

```python
# Bad
# Ask for an attachment only when one is missing, and include field names only
# when required fields remain. Building the sentence from the non-empty values
# avoids extra punctuation in attachment-only replies.

# Good
# Add `or` only when the reply asks for both an attachment and missing fields.
requested_inputs = [text for text in (attachment_text, missing_fields_text) if text]
requested_inputs_text = " or ".join(requested_inputs)
```

## Docstrings

```python
# Bad
def is_adult(age: int) -> bool:
    """Check if user is adult."""
    return age >= 18

# Good
def count_lines(path: str) -> int:
    """Count newline bytes (\n); carriage returns are not treated as line ends."""
    ...
```

```python
def process_payment(amount: Decimal, user: User) -> bool:
    """Deduct `amount` from user balance, persist, then send receipt.

    Order is critical: balance must be saved before receipt fires.
    Receipt failure is best-effort; payment is already committed.

    Raises:
        ValueError: amount is negative.
        InsufficientFundsError: user.balance < amount.
    """
    ...
```
