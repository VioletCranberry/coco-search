;; @doc Python symbol extraction: classes, functions, methods

;; Class definitions
(class_definition
  name: (identifier) @name) @definition.class

;; Function definitions (top-level and methods)
(function_definition
  name: (identifier) @name) @definition.function
