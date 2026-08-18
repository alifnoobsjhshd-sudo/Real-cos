---
name: Playlist queue progression
description: Constraint for playlist playback startup and track-end progression.
---

Playlist playback must resolve the tracks that will be queued before starting the first track; starting playback while searches are still filling the queue can make the track-end handler observe an empty queue and stop the playlist early.

**Why:** A short first track can finish before asynchronous Lavalink searches complete, creating a false playlist-exhausted state.

**How to apply:** When changing playlist playback or jump/restart behavior, seed the player queue before calling `player.play()` and keep the track-display lifecycle tied to track-start/track-end events.