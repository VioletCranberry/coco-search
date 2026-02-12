;; @doc CSS symbol extraction: rule sets (class/ID/element selectors), keyframes, media queries

;; Rule sets with class selectors (.header, .btn, etc.)
(rule_set
  (selectors
    (class_selector
      (class_name) @name))) @definition.class

;; Rule sets with ID selectors (#main, #sidebar, etc.)
(rule_set
  (selectors
    (id_selector
      (id_name) @name))) @definition.class

;; Rule sets with element/tag selectors (body, h1, div, etc.)
(rule_set
  (selectors
    (tag_name) @name)) @definition.class

;; @keyframes animations
(keyframes_statement
  (keyframes_name) @name) @definition.function

;; @media queries
(media_statement
  (feature_query) @name) @definition.class
