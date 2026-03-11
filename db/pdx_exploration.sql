-- PDX Strict Schema Exploration: Codebase-as-Data
-- Focus: Self-Explanatory, No Options, Zero-Ambiguity

CREATE TABLE IF NOT EXISTS api.pdx_function_registry (
    function_id                  BIGSERIAL PRIMARY KEY,
    self_explanatory_name        TEXT NOT NULL UNIQUE, 
    mathematical_formula         TEXT NOT NULL,        
    python_source_code           TEXT NOT NULL,        
    
    -- INPUTS: Mandatory
    input_parameter_definitions  JSONB NOT NULL,       
    
    -- OUTPUTS: Mandatory
    expected_return_type         TEXT NOT NULL,        
    known_test_outcome           JSONB NOT NULL,        
    
    -- ERROR GUIDANCE: Mandatory
    error_resolution_catalog     JSONB NOT NULL,        
    
    -- TRACEABILITY
    virtual_file_path            TEXT NOT NULL,
    virtual_line_number          INTEGER NOT NULL
);

-- SEEDING A CLEAR, SELF-EXPLANATORY EXAMPLE
INSERT INTO api.pdx_function_registry (
    self_explanatory_name,
    mathematical_formula,
    python_source_code,
    input_parameter_definitions,
    expected_return_type,
    known_test_outcome,
    error_resolution_catalog,
    virtual_file_path,
    virtual_line_number
) VALUES (
    'sum_of_two_decimal_floating_point_values',
    'x + y',
    'def sum_of_two_decimal_floating_point_values(first_value: float, second_value: float) -> float:\n    return first_value + second_value',
    '[{"name": "first_value", "type": "float"}, {"name": "second_value", "type": "float"}]',
    'float',
    '{"inputs": {"first_value": 1.5, "second_value": 2.5}, "output": 4.0}',
    '{"TypeError": "Inputs must be floating point numbers. Fix: Cast inputs using float() before calling."}',
    'src/math_operations.py',
    1
);