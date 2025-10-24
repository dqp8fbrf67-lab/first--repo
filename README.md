# First Repo

This repository is currently being used for experimentation and testing.

## Troubleshooting: `OPENAI_API_KEY` Not Set

If you see an error similar to:

```
openai.error.OpenAIError: api_key must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable.
```

follow the steps below to correctly configure the `OPENAI_API_KEY` environment variable on Windows.

1. **PowerShell (recommended)**
   ```powershell
   $env:OPENAI_API_KEY = "sk-..."   # sets it for the current session
   ```

   To make it available in every new PowerShell window, add the same line to your PowerShell profile or use:
   ```powershell
   setx OPENAI_API_KEY "sk-..."
   ```
   After running `setx`, close and reopen PowerShell so the new variable is loaded.

2. **Command Prompt (cmd.exe)**
   ```cmd
   set OPENAI_API_KEY=sk-...
   ```
   This sets the variable for the current Command Prompt session only.

3. **Verify the variable is set**
   ```powershell
   [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "Process")
   ```
   or reopen a new session and run `echo $env:OPENAI_API_KEY`.

Once the environment variable is set, rerun your Python script:

```powershell
python bot.py
```

If the error persists, confirm there are no leading/trailing quotes stored in the variable and that you restarted the shell after using `setx`.
