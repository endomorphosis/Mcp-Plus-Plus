# Security Guidelines for MCP

Comprehensive security guidelines for implementing and deploying Model Context Protocol servers and clients.

## Table of Contents

1. [Security Principles](#security-principles)
2. [Authentication](#authentication)
3. [Authorization](#authorization)
4. [Input Validation](#input-validation)
5. [Output Sanitization](#output-sanitization)
6. [Transport Security](#transport-security)
7. [Secrets Management](#secrets-management)
8. [Common Vulnerabilities](#common-vulnerabilities)
9. [Security Checklist](#security-checklist)

## Security Principles

### Defense in Depth

Implement multiple layers of security controls:

1. **Network Layer**: Firewalls, VPNs, network segmentation
2. **Transport Layer**: TLS/SSL encryption
3. **Application Layer**: Authentication, authorization, input validation
4. **Data Layer**: Encryption at rest, secure storage

### Least Privilege

Grant minimum necessary permissions:

```python
class Permission(Enum):
    READ_PUBLIC = "read:public"
    READ_PRIVATE = "read:private"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"

def check_permission(user: User, required: Permission) -> bool:
    """Verify user has required permission."""
    return required in user.permissions
```

### Fail Secure

When errors occur, default to denying access:

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict, user: User):
    try:
        # Check permissions
        if not has_permission(user, name):
            raise PermissionError("Access denied")
        
        return await execute_tool(name, arguments)
    except Exception as e:
        # Log the error
        logger.error(f"Tool execution failed: {e}")
        # Deny access by default
        raise PermissionError("Operation not permitted")
```

### Security by Design

Build security in from the start, not as an afterthought.

## Authentication

### API Keys

Simple authentication for server-to-server communication:

```python
import secrets
import hashlib

class APIKeyAuth:
    def __init__(self, valid_keys: set[str]):
        self.valid_keys = {self.hash_key(k) for k in valid_keys}
    
    def hash_key(self, key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def verify(self, provided_key: str) -> bool:
        """Verify provided API key."""
        hashed = self.hash_key(provided_key)
        return hashed in self.valid_keys
    
    @staticmethod
    def generate_key() -> str:
        """Generate a secure API key."""
        return secrets.token_urlsafe(32)

# Usage
auth = APIKeyAuth(valid_keys={os.getenv("API_KEY")})

@server.middleware()
async def authenticate(request, call_next):
    api_key = request.headers.get("X-API-Key")
    
    if not auth.verify(api_key):
        raise PermissionError("Invalid API key")
    
    return await call_next(request)
```

### JWT (JSON Web Tokens)

For user authentication with claims:

```python
import jwt
from datetime import datetime, timedelta

class JWTAuth:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_token(self, user_id: str, permissions: list[str]) -> str:
        """Create JWT token."""
        payload = {
            "user_id": user_id,
            "permissions": permissions,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> dict:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise PermissionError("Token expired")
        except jwt.InvalidTokenError:
            raise PermissionError("Invalid token")

# Usage
jwt_auth = JWTAuth(secret_key=os.getenv("JWT_SECRET"))

@server.middleware()
async def authenticate(request, call_next):
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise PermissionError("Missing or invalid authorization header")
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    payload = jwt_auth.verify_token(token)
    
    request.user = User(
        id=payload["user_id"],
        permissions=set(payload["permissions"])
    )
    
    return await call_next(request)
```

### OAuth 2.0

For delegated authorization:

```python
from authlib.integrations.httpx_client import AsyncOAuth2Client

class OAuth2Auth:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_endpoint: str
    ):
        self.client = AsyncOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint=token_endpoint
        )
    
    async def get_access_token(self, code: str) -> str:
        """Exchange authorization code for access token."""
        token = await self.client.fetch_token(
            self.token_endpoint,
            code=code
        )
        return token["access_token"]
    
    async def verify_token(self, access_token: str) -> dict:
        """Verify access token with authorization server."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://oauth.provider.com/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            return response.json()
```

### Mutual TLS (mTLS)

For strong mutual authentication:

```python
import ssl

def create_ssl_context(
    cert_file: str,
    key_file: str,
    ca_file: str
) -> ssl.SSLContext:
    """Create SSL context for mTLS."""
    context = ssl.create_default_context(
        purpose=ssl.Purpose.CLIENT_AUTH,
        cafile=ca_file
    )
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    context.verify_mode = ssl.CERT_REQUIRED
    return context

# Usage with server
ssl_context = create_ssl_context(
    cert_file="server.crt",
    key_file="server.key",
    ca_file="ca.crt"
)
```

## Authorization

### Role-Based Access Control (RBAC)

Define roles with specific permissions:

```python
from enum import Enum
from typing import Set

class Role(Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"

class Permission(Enum):
    READ_RESOURCES = "resources:read"
    WRITE_RESOURCES = "resources:write"
    CALL_TOOLS = "tools:call"
    MANAGE_USERS = "users:manage"

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.READ_RESOURCES,
    },
    Role.EDITOR: {
        Permission.READ_RESOURCES,
        Permission.WRITE_RESOURCES,
        Permission.CALL_TOOLS,
    },
    Role.ADMIN: {
        Permission.READ_RESOURCES,
        Permission.WRITE_RESOURCES,
        Permission.CALL_TOOLS,
        Permission.MANAGE_USERS,
    },
}

class User:
    def __init__(self, id: str, role: Role):
        self.id = id
        self.role = role
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in ROLE_PERMISSIONS[self.role]

# Usage
@server.call_tool()
async def call_tool(name: str, arguments: dict, user: User):
    if not user.has_permission(Permission.CALL_TOOLS):
        raise PermissionError("User lacks permission to call tools")
    
    return await execute_tool(name, arguments)
```

### Attribute-Based Access Control (ABAC)

Fine-grained access control based on attributes:

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class AccessPolicy:
    resource_type: str
    action: str
    conditions: dict[str, Any]

def evaluate_policy(
    user: User,
    resource: Resource,
    action: str,
    policy: AccessPolicy
) -> bool:
    """Evaluate access policy."""
    # Check resource type
    if resource.type != policy.resource_type:
        return False
    
    # Check action
    if action != policy.action:
        return False
    
    # Evaluate conditions
    for key, value in policy.conditions.items():
        if key == "owner":
            if resource.owner != user.id:
                return False
        elif key == "department":
            if user.department != value:
                return False
        elif key == "time_range":
            current_hour = datetime.now().hour
            if not (value["start"] <= current_hour < value["end"]):
                return False
    
    return True

# Example policy: Users can only read their own resources during business hours
policy = AccessPolicy(
    resource_type="document",
    action="read",
    conditions={
        "owner": True,
        "time_range": {"start": 9, "end": 17}
    }
)
```

## Input Validation

### Schema Validation

Always validate against JSON schema:

```python
from jsonschema import validate, ValidationError, FormatChecker

def validate_tool_input(schema: dict, data: dict) -> None:
    """Validate input data against JSON schema."""
    try:
        validate(
            instance=data,
            schema=schema,
            format_checker=FormatChecker()
        )
    except ValidationError as e:
        raise ValueError(f"Invalid input: {e.message}")

# Example schema with strict validation
tool_schema = {
    "type": "object",
    "properties": {
        "email": {
            "type": "string",
            "format": "email",
            "maxLength": 100
        },
        "age": {
            "type": "integer",
            "minimum": 0,
            "maximum": 150
        },
        "url": {
            "type": "string",
            "format": "uri",
            "maxLength": 2000
        }
    },
    "required": ["email"],
    "additionalProperties": False  # Reject unknown properties
}
```

### Sanitization

Clean user inputs to prevent injection attacks:

```python
import re
import html
from pathlib import Path

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')
    
    # Remove null bytes
    filename = filename.replace('\x00', '')
    
    # Remove parent directory references
    filename = filename.replace('..', '')
    
    # Limit length
    if len(filename) > 255:
        raise ValueError("Filename too long")
    
    # Allow only alphanumeric, dash, underscore, and period
    if not re.match(r'^[\w\-. ]+$', filename):
        raise ValueError("Invalid characters in filename")
    
    return filename

def sanitize_sql_input(value: str) -> str:
    """Prevent SQL injection (prefer parameterized queries instead)."""
    # Remove SQL special characters
    dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'xp_', 'sp_']
    for char in dangerous_chars:
        if char in value:
            raise ValueError(f"Potentially dangerous character: {char}")
    return value

def sanitize_html(text: str) -> str:
    """Escape HTML to prevent XSS."""
    return html.escape(text)

def sanitize_shell_arg(arg: str) -> str:
    """Sanitize shell arguments (prefer using lists instead)."""
    # Remove shell metacharacters
    dangerous = ['$', '`', ';', '|', '&', '>', '<', '\n', '\r']
    for char in dangerous:
        if char in arg:
            raise ValueError(f"Dangerous shell character: {char}")
    return arg
```

### Type Validation

Enforce strict type checking:

```python
from typing import Union, Any
from decimal import Decimal

def validate_type(value: Any, expected_type: type) -> Any:
    """Validate value matches expected type."""
    if not isinstance(value, expected_type):
        raise TypeError(
            f"Expected {expected_type.__name__}, got {type(value).__name__}"
        )
    return value

def safe_int(value: Any, min_val: int = None, max_val: int = None) -> int:
    """Safely convert to integer with bounds checking."""
    try:
        result = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"Cannot convert to integer: {value}")
    
    if min_val is not None and result < min_val:
        raise ValueError(f"Value {result} below minimum {min_val}")
    
    if max_val is not None and result > max_val:
        raise ValueError(f"Value {result} above maximum {max_val}")
    
    return result

def safe_decimal(value: Any, precision: int = 2) -> Decimal:
    """Safely convert to Decimal for financial calculations."""
    try:
        result = Decimal(str(value))
        return result.quantize(Decimal(10) ** -precision)
    except Exception:
        raise ValueError(f"Cannot convert to Decimal: {value}")
```

## Output Sanitization

### Redact Sensitive Data

Remove sensitive information from outputs:

```python
import re
from typing import Pattern

class SensitiveDataRedactor:
    def __init__(self):
        self.patterns: list[tuple[Pattern, str]] = [
            # API keys
            (re.compile(r'\b[A-Za-z0-9]{32,}\b'), '[REDACTED_API_KEY]'),
            # Credit cards
            (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), '[REDACTED_CC]'),
            # SSN
            (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[REDACTED_SSN]'),
            # Email addresses
            (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[REDACTED_EMAIL]'),
            # IP addresses
            (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '[REDACTED_IP]'),
            # AWS keys
            (re.compile(r'AKIA[0-9A-Z]{16}'), '[REDACTED_AWS_KEY]'),
            # Private keys
            (re.compile(r'-----BEGIN.*PRIVATE KEY-----.*-----END.*PRIVATE KEY-----', re.DOTALL), '[REDACTED_PRIVATE_KEY]'),
        ]
    
    def redact(self, text: str) -> str:
        """Redact sensitive data from text."""
        for pattern, replacement in self.patterns:
            text = pattern.sub(replacement, text)
        return text

# Usage
redactor = SensitiveDataRedactor()

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    result = await execute_tool(name, arguments)
    
    # Redact sensitive data before returning
    if isinstance(result, str):
        result = redactor.redact(result)
    
    return result
```

### Limit Response Size

Prevent memory exhaustion:

```python
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB

def truncate_response(content: str, max_size: int = MAX_RESPONSE_SIZE) -> dict:
    """Truncate large responses."""
    if len(content) <= max_size:
        return {
            "content": content,
            "truncated": False
        }
    
    return {
        "content": content[:max_size],
        "truncated": True,
        "original_size": len(content),
        "message": f"Response truncated to {max_size} bytes"
    }
```

## Transport Security

### TLS/SSL Configuration

Secure communication channels:

```python
import ssl

def create_secure_ssl_context() -> ssl.SSLContext:
    """Create SSL context with strong security."""
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    # Use strong protocol
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    
    # Strong cipher suites
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    
    # Load certificates
    context.load_cert_chain('server.crt', 'server.key')
    
    return context
```

### HTTP Security Headers

Set security headers for HTTP transport:

```python
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

@server.middleware()
async def add_security_headers(request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response
```

## Secrets Management

### Environment Variables

Never hardcode secrets:

```python
import os
from dotenv import load_dotenv

# Load from .env file
load_dotenv()

# Required secrets
REQUIRED_SECRETS = ["API_KEY", "DATABASE_URL", "JWT_SECRET"]

for secret in REQUIRED_SECRETS:
    if not os.getenv(secret):
        raise ValueError(f"Missing required secret: {secret}")

API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
```

### Key Vault Integration

Use cloud key vaults for production:

```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

class KeyVaultManager:
    def __init__(self, vault_url: str):
        credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=credential)
    
    def get_secret(self, name: str) -> str:
        """Retrieve secret from Key Vault."""
        return self.client.get_secret(name).value
    
    def set_secret(self, name: str, value: str) -> None:
        """Store secret in Key Vault."""
        self.client.set_secret(name, value)

# Usage
vault = KeyVaultManager("https://your-vault.vault.azure.net/")
api_key = vault.get_secret("api-key")
```

### Secret Rotation

Implement regular secret rotation:

```python
from datetime import datetime, timedelta

class SecretRotationManager:
    def __init__(self, max_age_days: int = 90):
        self.max_age_days = max_age_days
        self.secrets = {}
    
    def should_rotate(self, secret_name: str) -> bool:
        """Check if secret should be rotated."""
        if secret_name not in self.secrets:
            return True
        
        age = datetime.now() - self.secrets[secret_name]["created_at"]
        return age > timedelta(days=self.max_age_days)
    
    async def rotate_secret(self, secret_name: str):
        """Rotate a secret."""
        if self.should_rotate(secret_name):
            new_secret = generate_secure_secret()
            await update_secret(secret_name, new_secret)
            self.secrets[secret_name] = {
                "created_at": datetime.now()
            }
```

## Common Vulnerabilities

### SQL Injection

**Vulnerable:**
```python
# DON'T DO THIS
query = f"SELECT * FROM users WHERE email = '{email}'"
```

**Secure:**
```python
# Use parameterized queries
query = "SELECT * FROM users WHERE email = ?"
cursor.execute(query, (email,))
```

### Cross-Site Scripting (XSS)

**Vulnerable:**
```python
# DON'T DO THIS
return f"<div>Welcome {user_input}</div>"
```

**Secure:**
```python
import html
return f"<div>Welcome {html.escape(user_input)}</div>"
```

### Path Traversal

**Vulnerable:**
```python
# DON'T DO THIS
file_path = f"/data/{user_filename}"
with open(file_path) as f:
    return f.read()
```

**Secure:**
```python
from pathlib import Path

base_dir = Path("/data")
file_path = (base_dir / user_filename).resolve()

# Ensure path is within base directory
if not file_path.is_relative_to(base_dir):
    raise ValueError("Invalid path")

with open(file_path) as f:
    return f.read()
```

### Command Injection

**Vulnerable:**
```python
# DON'T DO THIS
os.system(f"ping {user_host}")
```

**Secure:**
```python
import subprocess

# Use list form with no shell
result = subprocess.run(
    ["ping", "-c", "1", user_host],
    capture_output=True,
    text=True,
    timeout=5
)
```

## Security Checklist

### Development

- [ ] All inputs validated against JSON schema
- [ ] Sensitive data sanitized in outputs
- [ ] No secrets in source code
- [ ] Error messages don't leak information
- [ ] Dependencies regularly updated
- [ ] Security linters configured (bandit, safety)

### Authentication & Authorization

- [ ] Authentication required for all endpoints
- [ ] Strong password/key requirements
- [ ] JWT tokens with expiration
- [ ] Role-based or attribute-based access control
- [ ] API rate limiting implemented
- [ ] Session timeout configured

### Transport

- [ ] TLS 1.3 or higher required
- [ ] Valid SSL certificates
- [ ] Security headers configured
- [ ] CORS properly configured
- [ ] HTTP security headers set

### Data Protection

- [ ] Encryption at rest for sensitive data
- [ ] Encryption in transit (TLS)
- [ ] Sensitive data redacted from logs
- [ ] PII handling compliant with regulations
- [ ] Regular backups encrypted

### Monitoring

- [ ] Security event logging enabled
- [ ] Failed authentication attempts logged
- [ ] Anomaly detection configured
- [ ] Alert thresholds set
- [ ] Log retention policy defined

### Incident Response

- [ ] Incident response plan documented
- [ ] Security contacts defined
- [ ] Backup and recovery tested
- [ ] Breach notification procedure
- [ ] Post-incident review process

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Cloud Security Alliance](https://cloudsecurityalliance.org/)

## Reporting Security Issues

If you discover a security vulnerability, please report it to:

- Email: security@example.com
- Use encrypted communication for sensitive details
- Include: Description, impact, reproduction steps
- Expected response time: 48 hours

---

Previous: [API Reference](API_REFERENCE.md) | Next: [Contributing](CONTRIBUTING.md)
