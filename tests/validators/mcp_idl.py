"""
MCP-IDL Validator

Validates MCP-IDL (Profile A) payloads according to docs/spec/mcp-idl.md
"""

from typing import Any, Dict, List, Optional
import hashlib
import json
from .base_mcp import ValidationResult


class MCPIDLValidator:
    """
    Validates MCP-IDL interface descriptors and related messages.
    
    Based on: docs/spec/mcp-idl.md
    """
    
    REQUIRED_DESCRIPTOR_FIELDS = [
        'name',
        'namespace',
        'version',
        'methods',
        'errors',
        'requires',
        'compatibility',
    ]
    
    RECOMMENDED_DESCRIPTOR_FIELDS = [
        'semantic_tags',
        'observability',
        'interaction_patterns',
        'resource_cost_hints',
    ]
    
    def validate_descriptor(self, descriptor: Dict[str, Any]) -> ValidationResult:
        """
        Validate an interface descriptor.
        
        Args:
            descriptor: The interface descriptor payload
            
        Returns:
            ValidationResult with validation status
        """
        result = ValidationResult(is_valid=True, message_type='interface_descriptor')
        
        # Check required fields
        for field in self.REQUIRED_DESCRIPTOR_FIELDS:
            if field not in descriptor:
                result.add_error(f"Missing required field: {field}")
        
        # Check recommended fields
        for field in self.RECOMMENDED_DESCRIPTOR_FIELDS:
            if field not in descriptor:
                result.add_warning(f"Missing recommended field: {field}")
        
        # Validate specific field formats
        if 'name' in descriptor:
            if not isinstance(descriptor['name'], str) or not descriptor['name']:
                result.add_error("'name' must be a non-empty string")
        
        if 'namespace' in descriptor:
            if not isinstance(descriptor['namespace'], str):
                result.add_error("'namespace' must be a string")
        
        if 'version' in descriptor:
            if not isinstance(descriptor['version'], str):
                result.add_error("'version' must be a string")
            # Check semantic versioning format
            elif not self._is_valid_semver(descriptor['version']):
                result.add_warning(f"Version should follow semantic versioning: {descriptor['version']}")
        
        # Validate methods array
        if 'methods' in descriptor:
            if not isinstance(descriptor['methods'], list):
                result.add_error("'methods' must be an array")
            else:
                for i, method in enumerate(descriptor['methods']):
                    self._validate_method(method, i, result)
        
        # Validate errors array
        if 'errors' in descriptor:
            if not isinstance(descriptor['errors'], list):
                result.add_error("'errors' must be an array")
        
        # Validate requires array
        if 'requires' in descriptor:
            if not isinstance(descriptor['requires'], list):
                result.add_error("'requires' must be an array")
        
        # Validate compatibility object
        if 'compatibility' in descriptor:
            if not isinstance(descriptor['compatibility'], dict):
                result.add_error("'compatibility' must be an object")
            else:
                self._validate_compatibility(descriptor['compatibility'], result)
        
        # Compute interface_cid if descriptor is valid
        if result.is_valid:
            try:
                interface_cid = self.compute_interface_cid(descriptor)
                result.metadata['interface_cid'] = interface_cid
            except Exception as e:
                result.add_error(f"Failed to compute interface_cid: {e}")
        
        return result
    
    def _validate_method(
        self, 
        method: Dict[str, Any], 
        index: int, 
        result: ValidationResult
    ) -> None:
        """Validate a method definition."""
        if not isinstance(method, dict):
            result.add_error(f"Method at index {index} must be an object")
            return
        
        if 'name' not in method:
            result.add_error(f"Method at index {index} missing 'name' field")
        
        # Check for schema CIDs
        if 'input_schema_cid' not in method:
            result.add_warning(f"Method '{method.get('name', index)}' missing 'input_schema_cid'")
        
        if 'output_schema_cid' not in method:
            result.add_warning(f"Method '{method.get('name', index)}' missing 'output_schema_cid'")
    
    def _validate_compatibility(
        self, 
        compatibility: Dict[str, Any], 
        result: ValidationResult
    ) -> None:
        """Validate compatibility metadata."""
        if 'compatible_with' in compatibility:
            if not isinstance(compatibility['compatible_with'], list):
                result.add_error("'compatible_with' must be an array")
        
        if 'supersedes' in compatibility:
            if not isinstance(compatibility['supersedes'], list):
                result.add_error("'supersedes' must be an array")
    
    def _is_valid_semver(self, version: str) -> bool:
        """Check if version follows semantic versioning."""
        parts = version.split('.')
        if len(parts) != 3:
            return False
        return all(part.isdigit() for part in parts)
    
    def compute_interface_cid(self, descriptor: Dict[str, Any]) -> str:
        """
        Compute a content-addressed identifier for the interface descriptor.
        
        This is a simplified implementation. Production systems should use
        proper CID computation with canonical JSON or DAG-CBOR.
        
        Args:
            descriptor: The interface descriptor
            
        Returns:
            A CID-like string (simplified for testing)
        """
        # Canonicalize descriptor (sort keys, deterministic JSON)
        canonical = json.dumps(descriptor, sort_keys=True, separators=(',', ':'))
        
        # Compute SHA-256 hash
        hash_bytes = hashlib.sha256(canonical.encode('utf-8')).digest()
        
        # Convert to simplified CID format (bafy... prefix for testing)
        # Real implementation would use multibase + multihash + CID format
        import base64
        hash_b64 = base64.b32encode(hash_bytes).decode('ascii').lower().rstrip('=')
        return f"bafy{hash_b64}"
    
    def validate_interface_list_request(self, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate interfaces/list request.
        
        Args:
            params: Request parameters
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='interfaces/list')
        
        # interfaces/list typically has no required parameters
        # Optional filters can be validated here
        
        return result
    
    def validate_interface_get_request(self, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate interfaces/get request.
        
        Args:
            params: Request parameters
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='interfaces/get')
        
        if 'interface_cid' not in params:
            result.add_error("interfaces/get requires 'interface_cid' parameter")
        
        return result
    
    def validate_interface_compat_request(self, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate interfaces/compat request.
        
        Args:
            params: Request parameters
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='interfaces/compat')
        
        if 'interface_cid' not in params:
            result.add_error("interfaces/compat requires 'interface_cid' parameter")
        
        return result
    
    def validate_toolset_select_request(self, params: Dict[str, Any]) -> ValidationResult:
        """
        Validate interfaces/select request (toolset slicing).
        
        Args:
            params: Request parameters
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True, message_type='interfaces/select')
        
        # Optional parameters for toolset slicing
        if 'task_hint_cid' in params:
            result.metadata['has_task_hint'] = True
        
        if 'budget' in params:
            if not isinstance(params['budget'], (int, float)):
                result.add_error("'budget' parameter must be a number")
        
        return result
