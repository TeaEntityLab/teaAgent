# Proposal: Replace Hard-Coded Configuration with Plugin System

## Executive Summary
This proposal outlines a plan to create a plugin-based configuration system that allows dynamic registration of configuration keys, replacing the hard-coded configuration in `config_loader.py`.

## Problem Statement

### Current State
The `config_loader.py` module hard-codes all configuration keys, environment variable names, and default values in a `CONFIG_KEYS` dictionary. This makes it difficult to extend configuration without modifying the core module. There's no plugin or extension mechanism for adding new configuration keys.

### Impact
- **Hard-Coded Keys**: All configuration keys are hard-coded
- **No Extensibility**: No mechanism for plugins to add configuration
- **Maintenance Burden**: Adding new keys requires modifying core module
- **Tight Coupling**: Configuration is tightly coupled to implementation

## Proposed Solution

### Phase 1: Create ConfigurationSchema Class
1. **Create Class**: Create `ConfigurationSchema` class that can be extended
2. **Move Keys**: Move hard-coded keys to the schema
3. **Add Methods**: Add methods for dynamic key registration
4. **Add Tests**: Add unit tests for the schema

### Phase 2: Implement ConfigurationProvider Interface
1. **Create Interface**: Create `ConfigurationProvider` protocol
2. **Implement Providers**: Implement providers for environment variables, files, CLI args
3. **Add Tests**: Add unit tests for each provider
4. **Update Loading**: Update config loading to use providers

### Phase 3: Use Registry Pattern for Configuration Keys
1. **Create Registry**: Create `ConfigurationRegistry` for dynamic key registration
2. **Add Methods**: Add methods for plugins to register their configuration keys
3. **Add Tests**: Add unit tests for the registry
4. **Update Loading**: Update config loading to use the registry

### Phase 4: Create ConfigurationValidator
1. **Create Validator**: Create `ConfigurationValidator` for schema validation
2. **Implement Rules**: Implement validation rules for each configuration key
3. **Add Tests**: Add unit tests for validation
4. **Update Loading**: Update config loading to validate against schema

### Phase 5: Support Dynamic Configuration Key Registration
1. **Create Plugin Interface**: Create plugin interface for configuration extensions
2. **Add Hooks**: Add hooks for plugins to register their keys
3. **Add Tests**: Add integration tests for plugin registration
4. **Update Documentation**: Update documentation for plugin development

## Implementation Details

### ConfigurationSchema Class
```python
# config/schema.py
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from enum import Enum

class ConfigKeyType(Enum):
    """Configuration key types."""
    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float'
    BOOLEAN = 'boolean'
    LIST = 'list'
    DICT = 'dict'

@dataclass
class ConfigKey:
    """Configuration key definition."""
    name: str
    type: ConfigKeyType
    default: Any
    required: bool = False
    validator: Optional[Callable[[Any], bool]] = None
    description: str = ''
    env_var: Optional[str] = None
    cli_arg: Optional[str] = None

@dataclass
class ConfigurationSchema:
    """Configuration schema that can be extended."""
    
    keys: dict[str, ConfigKey] = field(default_factory=dict)
    
    def register_key(self, key: ConfigKey) -> None:
        """Register configuration key."""
        if key.name in self.keys:
            raise ValueError(f'Configuration key {key.name} already registered')
        self.keys[key.name] = key
    
    def get_key(self, name: str) -> Optional[ConfigKey]:
        """Get configuration key by name."""
        return self.keys.get(name)
    
    def validate(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate configuration against schema."""
        errors = []
        
        # Check required keys
        for key in self.keys.values():
            if key.required and key.name not in config:
                errors.append(f'Required key {key.name} is missing')
        
        # Validate key types and values
        for key_name, value in config.items():
            key = self.keys.get(key_name)
            if key is None:
                errors.append(f'Unknown configuration key: {key_name}')
                continue
            
            # Type validation
            if not self._validate_type(value, key.type):
                errors.append(f'Invalid type for {key_name}: expected {key.type.value}')
                continue
            
            # Custom validation
            if key.validator and not key.validator(value):
                errors.append(f'Validation failed for {key_name}')
        
        return len(errors) == 0, errors
    
    def _validate_type(self, value: Any, type_: ConfigKeyType) -> bool:
        """Validate value type."""
        if type_ == ConfigKeyType.STRING:
            return isinstance(value, str)
        elif type_ == ConfigKeyType.INTEGER:
            return isinstance(value, int)
        elif type_ == ConfigKeyType.FLOAT:
            return isinstance(value, (int, float))
        elif type_ == ConfigKeyType.BOOLEAN:
            return isinstance(value, bool)
        elif type_ == ConfigKeyType.LIST:
            return isinstance(value, list)
        elif type_ == ConfigKeyType.DICT:
            return isinstance(value, dict)
        return False
```

### ConfigurationProvider Interface
```python
# config/provider.py
from typing import Protocol, Any
from abc import ABC, abstractmethod

class ConfigurationProvider(Protocol):
    """Protocol for configuration providers."""
    
    def load(self) -> dict[str, Any]:
        """Load configuration."""
        ...

class FileConfigurationProvider:
    """Configuration provider from file."""
    
    def __init__(self, path: str | None = None):
        """Initialize file configuration provider."""
        self._path = path
    
    def load(self) -> dict[str, Any]:
        """Load configuration from file."""
        if self._path is None:
            return {}
        
        import json
        from pathlib import Path
        
        path = Path(self._path)
        if not path.exists():
            return {}
        
        with open(path) as f:
            return json.load(f)

class EnvironmentConfigurationProvider:
    """Configuration provider from environment variables."""
    
    def __init__(self, prefix: str = 'TEAAGENT_'):
        """Initialize environment configuration provider."""
        self._prefix = prefix
    
    def load(self) -> dict[str, Any]:
        """Load configuration from environment variables."""
        import os
        
        config = {}
        for key, value in os.environ.items():
            if key.startswith(self._prefix):
                config_key = key[len(self._prefix):].lower()
                config[config_key] = value
        return config

class CLIConfigurationProvider:
    """Configuration provider from command-line arguments."""
    
    def __init__(self, args: Any):
        """Initialize CLI configuration provider."""
        self._args = args
    
    def load(self) -> dict[str, Any]:
        """Load configuration from CLI arguments."""
        config = {}
        if hasattr(self._args, 'provider'):
            config['provider'] = self._args.provider
        if hasattr(self._args, 'model'):
            config['model'] = self._args.model
        # Add more as needed
        return config
```

### ConfigurationRegistry
```python
# config/registry.py
from typing import Any
from teaagent.config.schema import ConfigurationSchema, ConfigKey

class ConfigurationRegistry:
    """Registry for dynamic configuration key registration."""
    
    def __init__(self):
        """Initialize configuration registry."""
        self._schema = ConfigurationSchema()
        self._providers: list[Any] = []
    
    def register_key(self, key: ConfigKey) -> None:
        """Register configuration key."""
        self._schema.register_key(key)
    
    def register_provider(self, provider: Any) -> None:
        """Register configuration provider."""
        self._providers.append(provider)
    
    def load_configuration(self) -> dict[str, Any]:
        """Load configuration from all providers."""
        config = {}
        
        # Load from each provider
        for provider in self._providers:
            provider_config = provider.load()
            config.update(provider_config)
        
        # Apply defaults for missing keys
        for key in self._schema.keys.values():
            if key.name not in config and key.default is not None:
                config[key.name] = key.default
        
        # Validate configuration
        valid, errors = self._schema.validate(config)
        if not valid:
            raise ValueError(f'Configuration validation failed: {errors}')
        
        return config
    
    def get_schema(self) -> ConfigurationSchema:
        """Get configuration schema."""
        return self._schema
```

### ConfigurationValidator
```python
# config/validator.py
from typing import Any, Callable
from teaagent.config.schema import ConfigurationSchema, ConfigKey, ConfigKeyType

class ConfigurationValidator:
    """Validator for configuration values."""
    
    def __init__(self, schema: ConfigurationSchema):
        """Initialize configuration validator."""
        self._schema = schema
    
    def validate(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate configuration against schema."""
        return self._schema.validate(config)
    
    @staticmethod
    def create_string_validator(
        min_length: int = 0,
        max_length: int | None = None,
        pattern: str | None = None,
    ) -> Callable[[Any], bool]:
        """Create string validator."""
        import re
        
        def validator(value: Any) -> bool:
            if not isinstance(value, str):
                return False
            if len(value) < min_length:
                return False
            if max_length is not None and len(value) > max_length:
                return False
            if pattern is not None and not re.match(pattern, value):
                return False
            return True
        
        return validator
    
    @staticmethod
    def create_integer_validator(
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> Callable[[Any], bool]:
        """Create integer validator."""
        def validator(value: Any) -> bool:
            if not isinstance(value, int):
                return False
            if min_value is not None and value < min_value:
                return False
            if max_value is not None and value > max_value:
                return False
            return True
        
        return validator
```

### Plugin Interface
```python
# config/plugin.py
from typing import Protocol
from teaagent.config.schema import ConfigKey

class ConfigurationPlugin(Protocol):
    """Protocol for configuration plugins."""
    
    def register_configuration_keys(
        self,
        registry: Any,
    ) -> None:
        """Register configuration keys."""
        ...

class PluginManager:
    """Manager for configuration plugins."""
    
    def __init__(self):
        """Initialize plugin manager."""
        self._plugins: list[ConfigurationPlugin] = []
    
    def register_plugin(self, plugin: ConfigurationPlugin) -> None:
        """Register configuration plugin."""
        self._plugins.append(plugin)
    
    def load_plugins(self, registry: Any) -> None:
        """Load all plugins and register their configuration keys."""
        for plugin in self._plugins:
            plugin.register_configuration_keys(registry)
```

## Migration Plan

### Step 1: Create ConfigurationSchema
1. Create `ConfigurationSchema` class
2. Move hard-coded keys to schema
3. Add unit tests for schema
4. Update config loading to use schema

### Step 2: Create ConfigurationProviders
1. Create `ConfigurationProvider` interface
2. Implement providers for different sources
3. Add unit tests for each provider
4. Update config loading to use providers

### Step 3: Create ConfigurationRegistry
1. Create `ConfigurationRegistry` class
2. Add methods for dynamic key registration
3. Add unit tests for registry
4. Update config loading to use registry

### Step 4: Create ConfigurationValidator
1. Create `ConfigurationValidator` class
2. Implement validation rules
3. Add unit tests for validation
4. Update config loading to validate

### Step 5: Create Plugin Interface
1. Create plugin interface
2. Add hooks for plugin registration
3. Add integration tests for plugins
4. Update documentation for plugin development

### Step 6: Update Callers
1. Update callers to use registry
2. Update callers to use providers
3. Add tests for new patterns
4. Update documentation

## Risk Mitigation

### Backward Compatibility
- Maintain backward compatibility during transition
- Keep hard-coded keys working with deprecation warnings
- Provide migration guide for breaking changes

### Testing
- Add comprehensive unit tests before refactoring
- Add integration tests for plugin system
- Run full test suite after each phase

### Feature Flags
- Use feature flags to enable new implementation gradually
- Allow rollback if issues arise
- Monitor metrics for configuration loading

## Timeline

### Phase 1: Create ConfigurationSchema (1 week)
- Week 1: Create schema, move keys, add tests

### Phase 2: Create ConfigurationProviders (1 week)
- Week 2: Create providers, add tests, update loading

### Phase 3: Create ConfigurationRegistry (1 week)
- Week 3: Create registry, add tests, update loading

### Phase 4: Create ConfigurationValidator (1 week)
- Week 4: Create validator, add tests, update loading

### Phase 5: Create Plugin Interface (1 week)
- Week 5: Create plugin interface, add tests, update documentation

### Phase 6: Update Callers and Documentation (1 week)
- Week 6: Update callers, add tests, update documentation

## Success Criteria

- ✅ No hard-coded configuration keys
- ✅ Dynamic configuration key registration supported
- ✅ Plugin system for configuration extensions
- ✅ Schema validation implemented
- ✅ All tests passing
- ✅ No breaking changes to public API
- ✅ Documentation updated
- ✅ Migration guide provided

## Alternatives Considered

### Alternative 1: Keep Hard-Coded Configuration
- **Pros**: No changes required
- **Cons**: Not extensible, maintenance burden
- **Decision**: Rejected - creates long-term maintenance burden

### Alternative 2: Use YAML/JSON Config Files Only
- **Pros**: Simple implementation
- **Cons**: Loses flexibility, no plugin support
- **Decision**: Rejected - insufficient for needs

### Alternative 3: Use Framework-Level Configuration Library
- **Pros**: Off-the-shelf solution
- **Cons**: Adds dependency, may not fit needs
- **Decision**: Rejected - custom solution better suited

## References
- ADR-006: Replace hard-coded configuration with plugin system
- Current implementation in `config_loader.py`
- Configuration management best practices
