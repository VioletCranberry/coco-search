;; @doc Scala symbol extraction: classes, traits, objects, methods, functions, type aliases

;; Methods (function_definition inside template_body — classes, traits, objects)
(template_body (function_definition name: (identifier) @name) @definition.method)

;; Abstract methods (function_declaration inside template_body)
(template_body (function_declaration name: (identifier) @name) @definition.method)

;; Top-level functions
(compilation_unit (function_definition name: (identifier) @name) @definition.function)

;; Class definitions (includes case class, abstract class)
(class_definition name: (identifier) @name) @definition.class

;; Trait definitions (includes sealed trait)
(trait_definition name: (identifier) @name) @definition.trait

;; Object definitions (includes case object)
(object_definition name: (identifier) @name) @definition.class

;; Type aliases
(type_definition name: (type_identifier) @name) @definition.type
