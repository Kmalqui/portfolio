use scripting additions

on run
    set payloadFolder to POSIX path of (path to resource "Payload")
    set meetingSource to payloadFolder & "MeetingScribe.app"
    set ollamaSource to payloadFolder & "Ollama.app"
    set userOllama to (POSIX path of (path to home folder)) & "Applications/Ollama.app"

    set ollamaProbe to "if [ -d /Applications/Ollama.app ] || [ -d " & quoted form of userOllama & " ] || [ -x /opt/homebrew/bin/ollama ] || [ -x /usr/local/bin/ollama ]; then echo yes; else echo no; fi"
    set ollamaWasPresent to ((do shell script ollamaProbe) is "yes")

    set installCommand to "/usr/bin/ditto " & quoted form of meetingSource & " /Applications/MeetingScribe.app"
    if not ollamaWasPresent then
        set installCommand to installCommand & " && /usr/bin/ditto " & quoted form of ollamaSource & " /Applications/Ollama.app"
    end if

    try
        do shell script installCommand with administrator privileges
    on error errorMessage
        display dialog "MeetingScribe could not finish installing." & return & return & errorMessage buttons {"OK"} default button "OK" with icon stop
        return
    end try

    do shell script "/usr/bin/open -R /Applications/MeetingScribe.app"
    if ollamaWasPresent then
        set ollamaResult to "Your existing Ollama installation was kept."
    else
        set ollamaResult to "The bundled Ollama app was installed too."
    end if

    display dialog "MeetingScribe is installed in Applications." & return & return & ollamaResult & return & return & "To open this community beta the first time, Control-click MeetingScribe, choose Open, and confirm." buttons {"Done"} default button "Done" with title "MeetingScribe is ready"
end run
