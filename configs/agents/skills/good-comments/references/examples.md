# Comprehensive Comment Examples

This file contains detailed before/after examples for reference. Load when you need additional examples beyond those in SKILL.md.

## Complete Class Refactoring Example

### Before: Over-commented, Poor Quality

```python
# User class
class User:
    # Constructor method
    def __init__(self, name, email, age):
        # Set the user's name
        self.name = name
        # Set the user's email address
        self.email = email
        # Set the user's age
        self.age = age
        # Set creation timestamp
        self.created = datetime.now()
    
    # Method to get the user's name
    def get_name(self):
        # Return the name
        return self.name
    
    # Method to get the user's email
    def get_email(self):
        # Return the email
        return self.email
    
    # Method to check if email is valid
    def is_valid_email(self):
        # Check if the @ symbol is in the email
        if '@' in self.email:
            # If yes, return True
            return True
        # Otherwise return False
        return False
    
    # Method to check if user is adult
    def is_adult(self):
        # Check if age is 18 or above
        if self.age >= 18:
            # Return True if adult
            return True
        # Return False if not adult
        return False
```

### After: Well-commented, High Quality

```python
class User:
    """
    Represents a registered user in the authentication system.
    
    Attributes:
        name: Full name of the user
        email: Email address (validated on creation)
        age: User's age in years
        created: UTC timestamp of user creation
    
    Note:
        Email validation is intentionally simple (@ check only).
        Production systems should use email-validator library.
    """
    
    def __init__(self, name: str, email: str, age: int):
        self.name = name
        self.email = email
        self.age = age
        self.created = datetime.now()
    
    def is_valid_email(self) -> bool:
        """
        Validate email format using basic @ symbol check.
        
        Returns:
            bool: True if email contains @, False otherwise
            
        Note:
            This is a minimal check for demo purposes. For RFC 5322
            compliance, use the email-validator library instead.
        """
        return '@' in self.email
    
    def is_adult(self) -> bool:
        """
        Check if user meets legal adult age requirement.
        
        Returns:
            bool: True if age >= 18, False otherwise
            
        Note:
            Age threshold fixed at 18 per US regulations. For
            international deployment, make threshold configurable.
        """
        return self.age >= 18
```

**Key improvements:**
- Removed all obvious comments
- Added comprehensive class docstring
- Added method docstrings with Returns and Note sections
- Kept only comments that add value (explaining constraints)
- Added type hints reducing need for parameter docs
- No getter docstrings (trivial methods don't need them)

## Algorithm Example with Strategic Comments

### Before: No Comments

```python
def find_duplicates(items):
    seen = {}
    duplicates = []
    for item in items:
        if item in seen:
            duplicates.append(item)
        else:
            seen[item] = True
    return duplicates
```

### After: Strategic Comments

```python
def find_duplicates(items):
    """
    Find duplicate items in a list while preserving order.
    
    Args:
        items: List of hashable items to check
        
    Returns:
        list: Duplicate items in order of first duplicate occurrence
        
    Note:
        Uses O(n) time and space. For memory-constrained environments
        with sorted input, consider two-pointer approach instead.
    """
    # Dictionary provides O(1) lookup vs O(n) for list.in
    # Critical for large datasets (10M+ items in production)
    seen = {}
    duplicates = []
    
    for item in items:
        if item in seen:
            duplicates.append(item)
        else:
            seen[item] = True
    
    return duplicates
```

**Key improvements:**
- Added docstring with complexity note
- Explained performance decision (dict vs list)
- Provided context about production scale
- No comments on obvious operations

## Complex Logic with Gotcha Comments

### Before: Unclear

```python
def process_payment(amount, user):
    if amount < 0:
        raise ValueError("Invalid amount")
    
    user.balance -= amount
    db.save(user)
    send_receipt(user, amount)
    
    return True
```

### After: Gotcha Documentation

```python
def process_payment(amount: float, user: User) -> bool:
    """
    Process payment and update user balance.
    
    Args:
        amount: Payment amount in USD (must be positive)
        user: User object with sufficient balance
        
    Returns:
        bool: True if payment processed successfully
        
    Raises:
        ValueError: If amount is negative
        InsufficientFundsError: If user balance insufficient
        
    Warning:
        Order of operations is critical:
        1. Validate amount first (prevents invalid DB writes)
        2. Update balance (must succeed before receipt)
        3. Save to DB (must succeed before receipt)
        4. Send receipt (failure here is acceptable)
        
        Changing this order can cause balance inconsistencies.
    """
    if amount < 0:
        raise ValueError("Amount must be positive")
    
    if user.balance < amount:
        raise InsufficientFundsError(f"Balance {user.balance} < {amount}")
    
    # CRITICAL: Update balance before saving to ensure
    # atomic operation. If save fails, balance won't persist.
    user.balance -= amount
    db.save(user)
    
    # Receipt delivery is best-effort. If this fails, payment
    # still succeeded. Customer support can resend receipts.
    try:
        send_receipt(user, amount)
    except EmailError:
        logger.warning(f"Receipt failed for user {user.id}")
    
    return True
```

**Key improvements:**
- Warning in docstring about operation order
- Inline comments explain critical ordering decisions
- Comment explains failure handling strategy
- Explains why receipt failure is acceptable

## API Constraint Documentation

### Before: Magic Number

```python
def fetch_users(page_size=50):
    return db.query(User).limit(page_size).all()
```

### After: Constraint Documentation

```python
# API rate limit: 1000 requests/hour with max 100 results/request
# 50 results chosen to balance between:
# - Network efficiency (fewer requests)
# - Memory usage (moderate batch size)  
# - API compliance (well under 100 limit with safety margin)
DEFAULT_PAGE_SIZE = 50

def fetch_users(page_size: int = DEFAULT_PAGE_SIZE) -> list[User]:
    """
    Fetch paginated user records from database.
    
    Args:
        page_size: Number of records per page (default: 50, max: 100)
        
    Returns:
        list[User]: User records for current page
        
    Note:
        Page size capped at 100 to comply with API rate limits.
        Exceeding this may result in 429 Too Many Requests errors.
    """
    # Enforce API maximum even if caller requests more
    safe_page_size = min(page_size, 100)
    return db.query(User).limit(safe_page_size).all()
```

**Key improvements:**
- Constant with comprehensive constraint explanation
- Docstring mentions rate limit implications
- Inline comment explains enforcement logic
- Explains the trade-offs in sizing decision

## Anti-Pattern: Compensating for Bad Code

### Before: Bad Code with Comments

```python
# Process the data
def proc(d):
    # Loop through data
    for i in d:
        # Check if valid
        if i > 0:
            # Print the value
            print(i)
```

### After: Self-Documenting Code

```python
def print_positive_values(values: list[int]) -> None:
    """Print all positive integers from the input list."""
    for value in values:
        if value > 0:
            print(value)
```

**Key lesson:** Don't use comments to explain bad code. Refactor instead.

## Anti-Pattern: Historical Comments

### Before: History in Comments

```python
# Created by John Doe on 2023-01-15
# Modified by Jane Smith on 2023-06-20 - added validation
# Modified by Bob Johnson on 2024-01-10 - fixed bug
def validate_input(data):
    # Old version used regex (too slow)
    # New version uses simple checks
    return data is not None and len(data) > 0
```

### After: Version Control

```python
def validate_input(data: str) -> bool:
    """
    Validate input data is non-empty.
    
    Args:
        data: Input string to validate
        
    Returns:
        bool: True if data is non-None and non-empty
    """
    return data is not None and len(data) > 0
```

**Key lesson:** Use git for history. Comments should document current state only.

## Docstring Style Comparison

### Google Style (Verbose but Clear)
```python
def calculate_bmi(weight, height):
    """Calculate Body Mass Index.
    
    Args:
        weight (float): Weight in kilograms
        height (float): Height in meters
        
    Returns:
        float: BMI value rounded to 2 decimals
        
    Raises:
        ValueError: If height is zero or negative
        
    Example:
        >>> calculate_bmi(70, 1.75)
        22.86
    """
    if height <= 0:
        raise ValueError("Height must be positive")
    return round(weight / (height ** 2), 2)
```

### NumPy Style (Detailed)
```python
def calculate_bmi(weight, height):
    """
    Calculate Body Mass Index.
    
    Parameters
    ----------
    weight : float
        Weight in kilograms
    height : float
        Height in meters
        
    Returns
    -------
    float
        BMI value rounded to 2 decimals
        
    Raises
    ------
    ValueError
        If height is zero or negative
        
    Examples
    --------
    >>> calculate_bmi(70, 1.75)
    22.86
    """
    if height <= 0:
        raise ValueError("Height must be positive")
    return round(weight / (height ** 2), 2)
```

### Minimal Style (Type Hints + Brief Docstring)
```python
def calculate_bmi(weight: float, height: float) -> float:
    """
    Calculate Body Mass Index from weight and height.
    
    Raises:
        ValueError: If height is zero or negative
    """
    if height <= 0:
        raise ValueError("Height must be positive")
    return round(weight / (height ** 2), 2)
```

**Recommendation:** Use type hints with minimal docstrings for simple functions. Reserve verbose styles for complex APIs.

## Summary Principles

1. **Code first, comments second** - Refactor before adding comments
2. **Quality over quantity** - One good comment beats ten bad ones
3. **WHY not WHAT** - Explain decisions and constraints, not operations
4. **Maintain or delete** - Update comments with code or remove them
5. **Trust the reader** - Don't over-explain to intelligent developers
6. **Question everything** - Each comment must justify its existence
