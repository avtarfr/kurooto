"""The senses (Brain, 0.8.0 stage 13): a body. Its own machine (interoception, on with Brain), what you are working
on (a text-free activity stream, opt-in) and the phone's sensors (each opt-in, on the phone and here). All of it stays
on this computer, minimised: raw events 7 days, then daily totals. Invariants I-11 and I-14 (what it learns about
actions and effects is about its own body only).

    store.py     raw events and daily totals
    intero.py    CPU/GPU temperature, memory, battery, disk, AI limits, the call line, the queue; the body model
    activity.py  window class, hashed titles, terminal folder, saves and commits in projects
    phone.py     the sealed bins from the phone's Senses
"""
