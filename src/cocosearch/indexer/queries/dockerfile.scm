;; @doc Dockerfile symbol extraction: build stages (FROM ... AS) and build arguments (ARG)

;; Build stages: FROM ... AS <alias>
(from_instruction
  as: (image_alias) @name) @definition.class

;; Build arguments: ARG <name>[=<default>]
(arg_instruction
  name: (unquoted_string) @name) @definition.variable
