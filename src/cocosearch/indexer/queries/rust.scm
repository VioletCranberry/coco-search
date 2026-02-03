;; @doc Rust symbol extraction: functions, methods, structs, traits, enums

;; Methods (function_item inside impl_item)
(impl_item
  (declaration_list
    (function_item
      (identifier) @name) @definition.method))

;; Top-level functions (not in impl)
(source_file
  (function_item
    (identifier) @name) @definition.function)

;; Struct definitions
(struct_item
  (type_identifier) @name) @definition.class

;; Trait definitions
(trait_item
  (type_identifier) @name) @definition.interface

;; Enum definitions
(enum_item
  (type_identifier) @name) @definition.class
