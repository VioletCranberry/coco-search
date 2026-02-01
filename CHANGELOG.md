# Changelog

All notable changes to CocoSearch will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Changed

- **BREAKING:** Environment variables renamed for consistency ([Phase 20](/.planning/phases/20-env-var-standardization/))

  | Old Name                 | New Name                  | Notes                     |
  |--------------------------|---------------------------|---------------------------|
  | `COCOINDEX_DATABASE_URL` | `COCOSEARCH_DATABASE_URL` | Required - database URL   |
  | `OLLAMA_HOST`            | `COCOSEARCH_OLLAMA_URL`   | Optional - Ollama API URL |

  **Migration:** Update your environment configuration to use the new variable names. The old names are no longer recognized.

### Added

- `cocosearch config check` command to validate environment variables without connecting to services
