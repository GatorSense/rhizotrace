```
            /  Pieces and junctions  /
                         │
                         ▼
┌────────────────────────────────────────────────┐
│            Build the junction graph            │
│    (each piece end to its nearest junction)    │
└────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│    Queue the pieces that end in a root tip     │
└────────────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────┐
│       Take the next piece from the queue       │ ◄──┐
└────────────────────────────────────────────────┘    │
                         │                            │
                         ▼                            │
┌────────────────────────────────────────────────┐    │
│     At each undecided junction it reaches:     │    │
│    angle between every pair of pieces there    │    │
└────────────────────────────────────────────────┘    │
                         │                            │
                         ▼                            │
┌────────────────────────────────────────────────┐    │
│         Join pairs, straightest first:         │    │
│        angle >= 150° (180° = straight),        │    │
│        or >= 90° if only 2 pieces meet;        │    │
│       each piece joins once per junction       │    │
└────────────────────────────────────────────────┘    │
                         │                            │
                         ▼                            │
┌────────────────────────────────────────────────┐    │
│           Mark the junction decided            │    │
└────────────────────────────────────────────────┘    │
                         │                            │
                         ▼                            │
┌────────────────────────────────────────────────┐    │
│       Joined pieces go back in the queue       │    │
│      if they reach an undecided junction       │    │
└────────────────────────────────────────────────┘    │
                         │                            │
            queue empty? ──► yes:  /  Branches  /     │
                         │ no                         │
                         └────────────────────────────┘
```
