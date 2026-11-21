## ADDED Requirements

### Requirement: Portal-owned read-only catalog MCP

Portal SHALL own a Streamable HTTP MCP interface on its existing HTTP listener.
Its lifecycle SHALL NOT depend on DSH or another MCP client launching a server
process. Existing REST/UI catalog behavior SHALL remain unchanged.

The interface SHALL expose only canonical catalog search, API-equivalent object
details with ordered columns, bounded canonical lineage and verified browser
links. It SHALL reuse existing catalog services rather than duplicate business
rules or perform loopback requests to its own REST API.

#### Scenario: Replace the AI client

- **GIVEN** Portal is running with MCP explicitly enabled
- **WHEN** a compatible authorized MCP client connects over Streamable HTTP
- **THEN** the client discovers the same read-only catalog tools independently of DSH
- **AND** the client does not start a Portal MCP server subprocess

#### Scenario: Search and inspect an object

- **GIVEN** an object and its columns exist in the canonical catalog
- **WHEN** an authorized MCP client searches and requests that object
- **THEN** the results preserve canonical identifiers, metadata, paging and freshness
- **AND** object details include all API-exposed fields and ordered columns
- **AND** no DWH scan, collection or SQL execution is initiated

#### Scenario: Preserve partial lineage

- **GIVEN** the canonical lineage response contains unresolved targets
- **WHEN** an authorized client requests lineage through MCP
- **THEN** canonical nodes, edge types, endpoints, unresolved targets and freshness remain available
- **AND** the response is identified as bounded catalog lineage rather than observed executions

#### Scenario: Return navigation without browser automation

- **GIVEN** an object exists and Portal has existing object and lineage UI routes
- **WHEN** an authorized client requests its links
- **THEN** the tool returns links to those routes without opening a browser
- **AND** arbitrary input URLs are not fetched and credentials are not included in links

### Requirement: Natural-language-first catalog capability discovery

The existing four tools SHALL expose descriptive parameter metadata and concrete
structured success schemas using canonical DTOs plus explicit redaction paths.
Read-only scope, search clamping, canonical JSON shapes and access protection
SHALL remain unchanged; validation failures SHALL be sanitized errors.

Server/profile guidance SHALL instruct the LLM to select available tools for
ordinary questions in the user's language without technical command prompts.
MCP SHALL remain a typed capability protocol, not a natural-language parser.
Identifiers SHALL be preserved, string-search limitations explained, and
ambiguous single-object candidates clarified instead of choosing the first.

DSH SHALL report actual global registration and scoped/step admission separately
using supported pinned APIs, with unknown states explicit. Health SHALL require
all four exact registrations rather than only process/guard health. Registration
or assembly evidence SHALL NOT claim to prove model selection or successful
reads. Missing capabilities SHALL NOT trigger invented resources or execution
fallbacks; resource discovery stays off and the exact guard stays unchanged.

#### Scenario: Natural-language question without tool names

- **GIVEN** the catalog chat has a tool-capable model and catalog access
- **WHEN** a user asks an ordinary multilingual object question
- **THEN** guidance directs model-selected calls from descriptions and schemas
- **AND** ambiguous matches are clarified and identifiers are not silently translated

#### Scenario: Structured canonical success or sanitized error

- **GIVEN** the client discovers concrete tool output schemas
- **WHEN** the catalog returns data or invalid output
- **THEN** success preserves masked canonical DTO shapes and invalid output is a sanitized error

#### Scenario: Guard activation without catalog registration

- **GIVEN** DSH has installed its guard but catalog registration is missing or partial
- **WHEN** readiness or scoped context is evaluated
- **THEN** missing/unknown availability is reported rather than successful catalog readiness
- **AND** model selection and actual catalog reads remain separately unproven

### Requirement: Explicit MCP read access mode

MCP SHALL have distinct interface-enablement and anonymous-read settings.
When anonymous reads are off, MCP SHALL require a dedicated MCP-only credential
for all protocol operations, including discovery. It SHALL NOT accept ordinary
Portal service keys or browser cookies as an implicit fallback. MCP credentials
SHALL NOT grant REST access. This scope SHALL NOT claim per-user isolation or OAuth.

As an explicitly approved temporary exception, anonymous-read mode SHALL permit
initialization, discovery and the same read-only catalog tools without a token.
It SHALL NOT enable additional tools or mutation capabilities. Operator guidance
SHALL disclose that anyone who can reach the endpoint can read its metadata.

#### Scenario: Reject unauthenticated discovery

- **GIVEN** MCP is enabled with anonymous reads off and a configured dedicated credential
- **WHEN** a request omits that credential or supplies an invalid credential
- **THEN** protocol discovery and tool calls are rejected before catalog access
- **AND** the response does not echo any supplied or configured credential

#### Scenario: No write surface

- **GIVEN** a client has a valid MCP credential or anonymous reads are enabled
- **WHEN** it discovers tools or requests an unsupported mutation operation
- **THEN** only the approved read-only catalog tools are exposed
- **AND** the unsupported operation cannot collect, mutate, execute SQL or access files

#### Scenario: Disabled interface fails closed

- **GIVEN** MCP is disabled, or anonymous reads are off and its required credential is unconfigured
- **WHEN** a client attempts to use MCP
- **THEN** no anonymous catalog access is available
- **AND** no default development credential enables MCP

#### Scenario: Temporary anonymous catalog reads

- **GIVEN** MCP is enabled and its anonymous-read setting is explicitly on
- **WHEN** a client connects without a credential
- **THEN** initialization, discovery and the read-only catalog tools are available
- **AND** no write, collection, SQL, shell or filesystem capabilities are exposed
- **AND** disabling anonymous reads restores the dedicated-credential requirement
