# Data Model

## Source JSON Structure

The M365 Copilot export is a single-line JSON file with this shape:

```
{
  "store": {
    "gptId": null,
    "zeroQuery": { ... },            // suggested questions — ignored
    "greeting": { ... },             // ignored
    "tenant": {                      // org branding — ignored
      "displayName": "...",
      ...
    },
    "clientCorrelationId": "uuid",   // ignored
    "rawConversationResponse": {
      "messages": [ <Message>... ]   // ← primary data
    }
  }
}
```

## Message Object (raw)

Every element in `messages[]` has this schema (fields marked `*` always present):

```
{
  "text": "...",                         // * message body — markdown (bot) or plain (user)
  "author": "user" | "bot" | "system",  // * role
  "from": { "id": "uuid" },             // user messages only — user identity
  "createdAt": "ISO-8601",              // * UTC creation time
  "timestamp": "ISO-8601",             // * local creation time (may include TZ offset)
  "locale": "en-us",
  "market": "en-us",
  "locationInfo": { ... },             // user messages only — ignored
  "messageId": "uuid",                 // * unique message ID
  "requestId": "uuid",                 // links user prompt to bot response
  "offense": "None",
  "contentOrigin": "officeweb" | "ModelSelector" | ...,
  "inputMethod": "Keyboard",           // user messages only
  "turnCount": <int>,                  // * which conversation turn (1-based)
  "storageMessageId": "string",
  "messageAnnotations": [ <Annotation>... ],  // user messages — file/image attachments
  "adaptiveCards": [ ... ],           // bot messages only — structured card (ignored; use text)
  "turnState": "Completed",           // bot messages only
  "responseIdentifier": "string",     // bot messages only
  "messageType": "Internal"           // system messages only — filter these out
}
```

## Annotation Object (raw)

Appears in `messageAnnotations[]` on user messages:

```
{
  "messageAnnotationType": "ImageFile",     // only observed type
  "messageAnnotationSource": "UserAnnotated",
  "id": "string",
  "messageAnnotationMetadata": {
    "@type": "File",
    "annotationType": "File",
    "source": 0,
    "fileName": "image.png",
    "fileType": "png",
    "fileContent": "data:image/jpeg;base64,..."  // embedded data URI
  }
}
```

---

## Normalised Python Model

After parsing, the raw JSON is mapped to these dataclasses:

```python
@dataclass
class Attachment:
    file_name: str          # original filename
    file_type: str          # extension (png, jpg, ...)
    data_uri: str           # full data: URI for embedding in <img src>

@dataclass
class Message:
    message_id: str         # UUID
    author: str             # "user" | "bot"  (system messages are dropped)
    text: str               # raw text (markdown for bot, plain for user)
    created_at: datetime    # parsed from createdAt (UTC)
    turn: int               # turnCount value
    attachments: list[Attachment]
```

## Entity References in User Text

User messages may contain inline XML-like tags:

```
<entity type='file' ReferenceId='uuid'>file</entity>
```

These are replaced during parsing with the resolved filename (looked up from `zeroQuery.data.items[].hydratedEntities`) or the literal text `[file]` when no match is found.

## Conversation Object

```python
@dataclass
class Conversation:
    messages: list[Message]   # only user + bot, chronological order
    title: str                # first user message, truncated to 80 chars
    started_at: datetime      # timestamp of first message
    ended_at: datetime        # timestamp of last message
```
