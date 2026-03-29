# copilot-chat-transcribe Walkthrough

*A linear demo of the `copilot-chat-transcribe` CLI tool -- installable from PyPI.*
<!-- showboat-id: bd4eade5-aa6a-462b-8777-6975b5d2d7ec -->

`copilot-chat-transcribe` converts Microsoft 365 Copilot chat sessions into clean, readable
transcripts. It has two modes: **file mode** (from a JSON export) and
**`--connect` mode** (live download from a running Edge browser).

## Step 1: Install and check version

```powershell
$env:PATH = $env:PATH + ";C:\Users\A549133\AppData\Roaming\Python\Python314\Scripts"
Set-Location "C:\Users\A549133\projects\chat"
.venv\Scripts\copilot-chat-transcribe.exe --version

```

```output
copilot-chat-transcribe 0.1.0
```

## Step 2: Inspect the input JSON

The sample file is a single-line JSON export from M365 Copilot.

```powershell
$f = "logs\get-single-conversation\5d41e7f4-5156-4a60-819c-c38184df70aa.json"
$size = (Get-Item $f).Length
Write-Host "File: $f"
Write-Host "Size: $size bytes"
$data = Get-Content $f -Raw | ConvertFrom-Json
$msgs = $data.store.rawConversationResponse.messages
Write-Host "Total messages: $($msgs.Count)"
$authors = $msgs | Group-Object author | Select-Object Name, Count | Format-Table -AutoSize | Out-String
Write-Host $authors.Trim()

```

```output
File: logs\get-single-conversation\5d41e7f4-5156-4a60-819c-c38184df70aa.json
Size: 120958 bytes
Total messages: 14
Name   Count
----   -----
bot        8
system     2
user       4
```

## Step 3: Parse the conversation

The parser drops system/internal messages, resolves file entity references,
and parses timestamps into UTC datetimes.

```powershell
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python.exe examples\demo_parse.py

```

```output
Title:       Help me draft bullet points to guide a discussion. Context: the executive wan...
Started:     2026-03-27 07:13 UTC
Ended:       2026-03-29 15:25 UTC
Messages:    12 (4 user, 8 bot)
Attachments: 2 image(s) embedded

  [1] user  turn=1  Help me draft bullet points to guide a discussion. Context: the e...
  [2] bot   turn=1  Here's a crisp, discussion-provoking set of bullet points you can...
  [3] user  turn=2  Some changes: The IT org is organized around Domains - Core flows...
  [4] bot   turn=2  Below is a clear, incremental storyline designed for a non-techni...
  [5] user  turn=3  Review the domain specific examples - a module should be identifi...
  [6] bot   turn=3  ...
  [7] bot   turn=3  Absolutely -- here is a refined, Domain-specific but DDD-aligned ...
  [8] bot   turn=3  ...
  [9] user  turn=4  A single slide demonstrating Module = Business Capability Product...
  [10] bot   turn=4  ...
  [11] bot   turn=4  Below are the three deliverables you requested, crafted so you ca...
  [12] bot   turn=4  ...
```

## Step 4: Convert to output folder (file mode)

`copilot-chat-transcribe` writes three files into the output folder: a self-contained HTML
transcript, a Markdown version, and the original JSON archived alongside.

```powershell
.venv\Scripts\copilot-chat-transcribe.exe `
    "logs\get-single-conversation\5d41e7f4-5156-4a60-819c-c38184df70aa.json" `
    -o docs\demo-output

```

```output
Parsing logs\get-single-conversation\5d41e7f4-5156-4a60-819c-c38184df70aa.json ...
  12 messages (4 user, 8 bot)
Rendering HTML ...
  Written: docs\demo-output\transcript.html
Rendering Markdown ...
  Written: docs\demo-output\transcript.md
  Copied:  docs\demo-output\conversation.json

Done -> docs\demo-output/
```

## Step 5: Verify the output folder

```powershell
Get-ChildItem "docs\demo-output" | Format-Table Name, Length -AutoSize
$html = Get-Content "docs\demo-output\transcript.html" -Raw
$size = [math]::Round((Get-Item "docs\demo-output\transcript.html").Length / 1KB, 1)
Write-Host "HTML size:     ${size} KB"
Write-Host "Valid DOCTYPE: $($html.TrimStart().StartsWith('<!DOCTYPE html>'))"
Write-Host "User bubbles:  $(([regex]::Matches($html, 'class=""message user""')).Count)"
Write-Host "Bot bubbles:   $(([regex]::Matches($html, 'class=""message bot""')).Count)"
Write-Host "Inline images: $(([regex]::Matches($html, '<img src=""data:')).Count)"
Write-Host "Headings:      $(([regex]::Matches($html, '<h[1-4]')).Count)"
Write-Host "Code blocks:   $(([regex]::Matches($html, '<pre>')).Count)"

```

```output
Name              Length
----              ------
conversation.json 120958
transcript.html    51572
transcript.md      21447

HTML size:     50.4 KB
Valid DOCTYPE: True
User bubbles:  4
Bot bubbles:   8
Inline images: 2
Headings:      53
Code blocks:   1
```

## Step 6: Live download via --connect

`--connect` mode attaches to a running MSEdge instance, navigates to
`chat.cloud.microsoft`, and fetches conversations using the browser's existing
auth session -- no credentials in Python.

```
copilot-chat-transcribe --connect -o my-chat
```

Interactive session (abridged):

```
Connecting to browser at http://localhost:9222 ...
Fetching conversation list ...
  Navigating to https://m365.cloud.microsoft/chat ...
  (Sign in if prompted -- waiting up to 2 minutes for conversation list ...)

Conversations 1-10 of 18:

  [ 1]  2026-03-29 15:34  Help me draft bullet points to guide a discussion.
  [ 2]  2026-03-26 14:09  Explain what each of these boxes mean -
  ...
  [10]  2026-03-14 12:45  Using this source - explain what is Digital Excell

Select [1-18], or [m]ore: m

Conversations 11-18 of 18:

  [11]  2026-03-14 12:30  Research this Powerpoint. Use this to create a not
  ...
  [18]  2026-03-09 17:37  List the key points for the Digital Technology (DT

Select [1-18]: 1

Downloading conversation: Help me draft bullet points to guide a discussion. ...
Parsing ...
  12 messages (4 user, 8 bot)
Rendering HTML ...
  Written: my-chat\transcript.html
Rendering Markdown ...
  Written: my-chat\transcript.md
  Written: my-chat\conversation.json

Done -> my-chat/
```

- Type `m` or `more` to page through older conversations (no re-fetch).
- Any number in `[1-N]` is valid at all times regardless of which page is shown.
- Up to 50 conversations are fetched in a single API call and paged locally.

