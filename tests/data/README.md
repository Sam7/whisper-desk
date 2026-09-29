# Speech fixture

`jfk.flac` is the 11-second public-domain excerpt of John F. Kennedy's 1961 inaugural address distributed in [OpenAI Whisper's test suite](https://github.com/openai/whisper/blob/main/tests/jfk.flac).

Expected speech: “And so, my fellow Americans, ask not what your country can do for you; ask what you can do for your country.”

The audio is retained in the repository so integration tests need only the model download, not a sample download. No microphone audio is retained by the application.
