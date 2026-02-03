;; @doc Java symbol extraction: classes, interfaces, enums, methods, constructors

;; Class declarations
(class_declaration
  name: (identifier) @name) @definition.class

;; Interface declarations
(interface_declaration
  name: (identifier) @name) @definition.interface

;; Enum declarations
(enum_declaration
  name: (identifier) @name) @definition.enum

;; Method declarations
(method_declaration
  name: (identifier) @name) @definition.method

;; Constructor declarations
(constructor_declaration
  name: (identifier) @name) @definition.method
