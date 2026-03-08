# PEP 8 and PEP 257 Comment Standards

Complete technical reference for Python commenting standards. Load when you need detailed PEP compliance information.

## PEP 8 Comment Guidelines

### Block Comments

Block comments apply to code that follows them and are indented to the same level.

**Format:**
- Start each line with `#` followed by a single space
- Paragraphs inside block comments separated by line containing single `#`
- Indented to same level as code they describe

**Examples:**

```python
# Single paragraph block comment explaining the following
# function's algorithm choice and trade-offs.
def process_data(items):
    ...

# Multi-paragraph block comment.
#
# This second paragraph provides additional context
# about edge cases or implementation details.
def complex_function():
    ...

# Indented block comment for nested code
class Example:
    def method(self):
        # This comment is indented to match the code
        # it describes within the method body
        value = compute()
        return value
```

### Inline Comments

Use inline comments sparingly. They should be separated by at least two spaces from the statement and use `# ` prefix.

**When to use:**
- Clarifying non-obvious line of code
- Explaining magic number or constant in context
- Warning about side effect

**When NOT to use:**
- Stating the obvious
- Instead of fixing unclear code
- Excessively (clutters code)

**Examples:**

```python
# Good inline comments
x = x + 1  # Compensate for border
count = 0  # Initialize before loop
value = calculate() or default  # Use default if None

# Bad inline comments
x = x + 1  # Increment x
i = 0  # Set i to zero
return True  # Return True
```

### Comment Formatting Rules

1. **Always use `# ` (hash + space)** at start of comment
2. **Use complete sentences** - Start with capital, end with period
3. **Two spaces** after sentence-ending period (if multiple sentences)
4. **Non-English speakers** - Write in English unless 120% sure code will never be read by non-native speakers

**Example:**
```python
# This is a properly formatted comment.  It uses complete
# sentences with proper capitalization and punctuation.
def example():
    pass
```

### Comment Language and Style

**Do:**
- Write in English (unless code is never for English speakers)
- Use complete sentences
- Be concise but clear
- Update comments when code changes

**Don't:**
- Write in multiple languages within same project
- Use sentence fragments (except inline comments)
- Leave outdated comments
- Use comments to explain poor variable names

## PEP 257 Docstring Conventions

### What is a Docstring?

A docstring is a string literal that occurs as first statement in module, function, class, or method definition. It becomes the `__doc__` special attribute of that object.

**Key points:**
- Use `"""triple double quotes"""`
- For consistency, always use `"""` even for one-line docstrings
- Can be accessed via `help()`, IDEs, documentation generators

### One-Line Docstrings

For simple, obvious cases where function fits on one line.

**Format rules:**
1. Triple quotes on same line as text
2. Prescriptive rather than descriptive (e.g., "Return..." not "Returns...")
3. No blank line before or after
4. End with period

**Examples:**

```python
def square(x):
    """Return the square of x."""
    return x * x

def get_username():
    """Return the current user's username."""
    return os.getenv('USER')

def is_empty(container):
    """Check if container has no elements."""
    return len(container) == 0
```

**Prescriptive mood examples:**
- "Return the pathname..." (not "Returns the pathname...")
- "Calculate the sum..." (not "Calculates the sum...")
- "Check if value..." (not "Checks if value...")

### Multi-Line Docstrings

For complex functions, classes, and modules.

**Format rules:**
1. Summary line, just like one-line docstring
2. Blank line after summary
3. More detailed description
4. Blank line before closing quotes (unless only summary + one line)
5. Closing quotes on separate line

**Function/Method docstring sections:**

```python
def complex_function(arg1, arg2, option=None):
    """
    Single-line summary of function purpose.
    
    More detailed description if needed. Explain what the
    function does, not how it does it (unless algorithm is
    noteworthy).
    
    Args:
        arg1: Description of first argument
        arg2: Description of second argument  
        option: Description of optional argument (default: None)
    
    Returns:
        Description of return value, including type and structure
    
    Raises:
        ErrorType: When and why this error occurs
        AnotherError: When and why this error occurs
    
    Note:
        Additional implementation details, caveats, or usage tips
        
    Example:
        >>> complex_function(1, 2)
        3
    """
    pass
```

**Class docstring format:**

```python
class Widget:
    """
    Summary of class purpose.
    
    Detailed description of class behavior, responsibilities,
    and relationship to other classes.
    
    Attributes:
        attr1: Description of attribute
        attr2: Description of attribute
        
    Note:
        Important information about class invariants or usage
    """
    
    def __init__(self, param):
        """
        Initialize Widget with param.
        
        Args:
            param: Description of initialization parameter
        """
        self.attr1 = param
```

**Module docstring format:**

```python
"""
Single-line summary of module purpose.

Longer description of module's role in the package. List the
classes, functions, and exceptions exported by the module with
one-line summaries.

Typical usage example:

  from module import important_function
  result = important_function(arg)
"""
```

### Docstring Content Guidelines

**Always document:**
- Purpose of function/class/module
- Parameters and their types/constraints
- Return values and their types/structure
- Exceptions that can be raised
- Side effects (file I/O, state changes, etc.)

**Don't document:**
- Implementation details (unless noteworthy algorithm)
- How to use private methods (unless for maintainers)
- Obvious parameters (e.g., "self")

**Special cases:**

```python
def __init__(self, param):
    """Initialize with param."""
    # Brief docstring acceptable for __init__
    
@property
def name(self):
    """str: The user's full name."""
    # Property docstrings can be brief with type prefix
    
def _internal_helper(data):
    """Helper function for internal use only."""
    # Private functions can have minimal docstrings
```

### Docstring Sections (Detailed)

**Args section:**
```python
"""
Args:
    param1 (int): Description of param1. Can span
        multiple lines with proper indentation.
    param2 (str, optional): Description. Defaults to None.
    *args: Variable length argument list description.
    **kwargs: Arbitrary keyword arguments description.
"""
```

**Returns section:**
```python
"""
Returns:
    bool: True if successful, False otherwise.
    
    # Or for complex returns:
    tuple: A tuple containing:
        - int: Status code
        - str: Status message
        - dict: Additional metadata
"""
```

**Raises section:**
```python
"""
Raises:
    ValueError: If input is negative
    FileNotFoundError: If file path doesn't exist
    TypeError: If param is not string or int
"""
```

**Note section:**
```python
"""
Note:
    This function modifies the database. Use with caution
    in production environments. Consider using a transaction
    wrapper for atomic operations.
"""
```

**Example section:**
```python
"""
Example:
    Basic usage:
    
    >>> from module import function
    >>> result = function(42)
    >>> print(result)
    'Success'
    
    Advanced usage with options:
    
    >>> result = function(42, option='advanced')
    >>> print(result)
    'Advanced success'
"""
```

## Common Docstring Styles Comparison

### PEP 257 (Standard)
```python
def func(arg1, arg2):
    """
    Summary line.
    
    More description here.
    
    Parameters:
        arg1: First argument
        arg2: Second argument
        
    Returns:
        Result description
    """
```

### Google Style
```python
def func(arg1, arg2):
    """Summary line.
    
    More description here.
    
    Args:
        arg1: First argument
        arg2: Second argument
        
    Returns:
        Result description
    """
```

### NumPy Style
```python
def func(arg1, arg2):
    """
    Summary line.
    
    More description here.
    
    Parameters
    ----------
    arg1 : type
        First argument
    arg2 : type
        Second argument
        
    Returns
    -------
    type
        Result description
    """
```

**Recommendation:** Choose one style and be consistent throughout project. Google style is most common in modern Python.

## Type Hints vs. Docstrings

With Python 3.5+ type hints, you can reduce docstring verbosity:

**Without type hints:**
```python
def greet(name):
    """
    Greet a user by name.
    
    Args:
        name (str): The user's name
        
    Returns:
        str: A greeting message
    """
    return f"Hello, {name}!"
```

**With type hints:**
```python
def greet(name: str) -> str:
    """Greet a user by name."""
    return f"Hello, {name}!"
```

**Best practice:** Use type hints for simple parameter/return types. Reserve docstring parameter documentation for complex types or when you need to explain constraints/formats.

## Special Method Docstrings

**`__init__` methods:**
```python
def __init__(self, value: int):
    """Initialize Counter with starting value."""
    # Don't document return value (always None)
```

**`__str__` and `__repr__`:**
```python
def __str__(self):
    """Return human-readable string representation."""
    
def __repr__(self):
    """Return unambiguous string representation for debugging."""
```

**Properties:**
```python
@property
def value(self):
    """int: The current counter value."""
    return self._value
    
@value.setter
def value(self, new_value):
    """Set counter value with validation."""
    if new_value < 0:
        raise ValueError("Value must be non-negative")
    self._value = new_value
```

## Docstring Testing with doctest

You can include testable examples in docstrings:

```python
def factorial(n):
    """
    Calculate factorial of n.
    
    >>> factorial(5)
    120
    >>> factorial(0)
    1
    >>> factorial(-1)
    Traceback (most recent call last):
        ...
    ValueError: n must be non-negative
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    return 1 if n == 0 else n * factorial(n - 1)
```

Run tests with: `python -m doctest module.py`

## Summary: PEP Standards Checklist

**Block Comments (PEP 8):**
- [ ] Start with `# ` (hash + space)
- [ ] Indented to match code level
- [ ] Use complete sentences
- [ ] Blank `#` line between paragraphs

**Inline Comments (PEP 8):**
- [ ] Minimum 2 spaces from code
- [ ] Start with `# ` (hash + space)
- [ ] Use sparingly

**Docstrings (PEP 257):**
- [ ] Use `"""triple double quotes"""`
- [ ] One-line: prescriptive mood, period at end
- [ ] Multi-line: summary, blank line, details, blank before close
- [ ] Document all public APIs
- [ ] Include Args, Returns, Raises as needed
- [ ] Use type hints to reduce parameter documentation

## Additional References

- **PEP 8 Full Text**: https://peps.python.org/pep-0008/
- **PEP 257 Full Text**: https://peps.python.org/pep-0257/
- **PEP 484 (Type Hints)**: https://peps.python.org/pep-0484/
- **Google Python Style Guide**: https://google.github.io/styleguide/pyguide.html
