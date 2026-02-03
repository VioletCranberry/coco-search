;; @doc Ruby symbol extraction: classes, modules, methods, singleton methods

;; Classes
(class
  name: (constant) @name) @definition.class

;; Modules
(module
  name: (constant) @name) @definition.module

;; Methods (instance methods)
(method
  name: (identifier) @name) @definition.method

;; Singleton methods (class methods)
(singleton_method
  name: (identifier) @name) @definition.method
