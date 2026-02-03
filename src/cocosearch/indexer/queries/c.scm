;; @doc C symbol extraction: functions, structs, enums, typedefs
;; Note: Only function_definition (with body) - not declarations

;; Functions (definitions only - have compound_statement body)
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @name)) @definition.function

;; Pointer function declarators: int *foo() {}
(function_definition
  declarator: (pointer_declarator
    declarator: (function_declarator
      declarator: (identifier) @name))) @definition.function

;; Structs (with body - excludes forward declarations)
(struct_specifier
  name: (type_identifier) @name
  body: (field_declaration_list)) @definition.struct

;; Enums
(enum_specifier
  name: (type_identifier) @name) @definition.enum

;; Typedefs
(type_definition
  declarator: (type_identifier) @name) @definition.type
