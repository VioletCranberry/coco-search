;; @doc Rust symbol extraction: functions, methods, structs, traits, enums

;; Function definitions (top-level)
(function_item
  name: (identifier) @name) @definition.function

;; Methods (inside impl blocks)
(impl_item
  body: (declaration_list
    (function_item
      name: (identifier) @name))) @definition.method

;; Struct definitions
(struct_item
  name: (type_identifier) @name) @definition.class

;; Trait definitions
(trait_item
  name: (type_identifier) @name) @definition.interface

;; Enum definitions
(enum_item
  name: (type_identifier) @name) @definition.class
