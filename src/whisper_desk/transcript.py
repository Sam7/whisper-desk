from .models import Word
import re


class Transcript:
    """Commit timestamped words outside the mutable tail; reconcile only that tail."""

    def __init__(self, config):
        self.config = config
        self.frontier = 0.0
        self.committed = []
        self.provisional = []
        self._anchors = []

    @property
    def text(self):
        return "".join(self.committed + self.provisional).strip()

    @property
    def start(self):
        return max(0.0, self.frontier - self.config.overlap)

    def finish(self, end):
        self.committed.extend(self.provisional)
        self.provisional = []
        self.frontier = end
        return self.text

    def update(self, words, offset, end, final=False):
        words = [Word(w.start + offset, w.end + offset, w.text) for w in words]
        # Whisper word times move between passes. Match the committed suffix in
        # the overlap before falling back to time, so shifting times cannot erase
        # the first uncommitted word or repeat the last committed word.
        def key(text):
            return re.sub(r"[^\w]", "", text).casefold()

        matched = None
        for length in range(min(12, len(self._anchors)), 0, -1):
            suffix = [key(w.text) for w in self._anchors[-length:]]
            for i in range(len(words) - length + 1):
                if (words[i + length - 1].end <= self.frontier + 1.0 and
                        [key(w.text) for w in words[i:i + length]] == suffix):
                    matched = i + length
                    break
            if matched is not None:
                break
        if matched is not None:
            words = words[matched:]
        else:
            words = [w for w in words if w.end > self.frontier + 0.001]
        cutoff = end if final else max(self.frontier, end - self.config.mutable_tail)
        candidates = [w for w in words if w.end <= cutoff]
        if final or end - offset >= self.config.max_window - 0.02:
            stable = candidates
        else:
            # Keep sentence context intact. Do not progressively crop through a
            # phrase just because a word has become old enough to commit.
            boundaries = [i for i, w in enumerate(candidates) if w.text.rstrip().endswith((".", "!", "?", "。", "！", "？"))]
            stable = candidates[:boundaries[-1] + 1] if boundaries else []
        self.committed.extend(w.text for w in stable)
        self._anchors.extend(stable)
        self._anchors = self._anchors[-12:]
        self.provisional = [w.text for w in words[len(stable):]]
        if stable:
            self.frontier = stable[-1].end
        elif not words and not self.provisional:
            self.frontier = cutoff
        if final:
            self.committed.extend(self.provisional)
            self.provisional = []
            self.frontier = end
        return self.text
