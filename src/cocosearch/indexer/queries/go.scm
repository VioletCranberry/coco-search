;; @doc Go symbol extraction: functions, methods, structs, interfaces

;; Function declarations (top-level functions)
(function_declaration
  name: (identifier) @name) @definition.function

;; Method declarations (functions with receivers)
(method_declaration
  name: (field_identifier) @name) @definition.method

;; Struct type declarations
(type_declaration
  (type_spec
    name: (type_identifier) @name
    type: (struct_type))) @definition.class

;; Interface type declarations
(type_declaration
  (type_spec
    name: (type_identifier) @name
    type: (interface_type))) @definition.interface
