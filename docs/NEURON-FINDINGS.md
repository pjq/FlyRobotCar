# Neuron Findings Used by FlyBobotCar

This note records findings gathered with OpenCLI against X/Twitter and Tavily Search. Social posts are implementation leads, not peer-reviewed evidence; claims are kept separate from confirmed primary/review sources.

## Primary candidate circuit

```text
looming visual stimulus
    ↓
LC4 + LPLC2
    ↓
MaleCNS / Giant Fiber pathway
    ↓
DNp01 + DNp10
    ↓
escape output
```

Tavily results consistently describe:

- **LC4** as encoding looming/visual expansion speed.
- **LPLC2** as encoding looming angular size and as necessary for Giant Fiber-mediated escape in the cited literature.
- **DNp01** as the Giant Fiber/escape command candidate.
- **DNp04** as a posture/escape candidate in related research.
- **TTMn** as a downstream jump-muscle motor neuron in the escape circuit.

References:

- [Ache et al., PubMed: Neural Basis for Looming Size and Velocity Encoding](https://pubmed.ncbi.nlm.nih.gov/30827912)
- [PLOS Biology: Drosophila escape motor circuit](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3003553)
- [University of Chicago: Control of Escape Behavior by Descending Neurons](https://knowledge.uchicago.edu/records/2k54k-vav60)
- [Drexel: Circuits for bilateral looming feature integration](https://researchdiscovery.drexel.edu/view/pdfCoverPage?instCode=01DRXU_INST&filePid=13405201130004721&download=true)

X implementation leads:

- [FlappyFly: LC4/LPLC2 → DNp01](https://x.com/i/status/2098081342416154670)
- [FLINCH: looming escape demo](https://x.com/i/status/2099544722515607924)
- [Chrome Dino looming demo](https://x.com/i/status/2098882531408187561)
- [X discussion describing LC4/LPLC2 and DNp01](https://x.com/i/status/2099256940174168471)

## Locomotion and steering candidates

- **DNg100**: forward locomotion / walking drive.
- **DNa02**: rapid steering, with bilateral activity useful for a left/right readout.
- **DNg13**: used by community implementations as an additional steering population.
- **DNa01**: related steering candidate, reported as slower/smaller steering in the eLife result.

References:

- [eLife: Neural circuit mechanisms for steering control](https://elifesciences.org/articles/102230)
- [The Transmitter: dedicated walking circuit and DNg100](https://www.thetransmitter.org/systems-neuroscience/long-sought-walking-circuit-found-in-fruit-flies)
- [X: DNg100 mapping caveat](https://x.com/i/status/2096487331096391762)

## Reward and plasticity candidates

Community experiments mention:

- **PAM/PAM11**: artificial reward/dopamine signal.
- **PPL1/PPL101**: aversive or punishment signal.
- **Kenyon cells → MBON**: candidate plasticity path.

These are not part of the current FlyBobotCar control loop. Adding them would create a separate learning experiment and must not be described as fixed-connectome behavior.

Reference lead:

- [FlyTok experiment description](https://x.com/i/status/2098359568799834310)

## What the code now does

`robot.py` loads the prepared MaleCNS annotation table and resolves these named populations to model indices:

```text
LC4, LPLC2
DNp01, DNp10
DNg100
DNa02_L, DNa02_R
DNg13_L, DNg13_R
```

At each model step:

1. The room camera produces the visual atlas.
2. The complete MaleCNS model propagates spikes.
3. The annotated DNg100 rolling activity becomes throttle; a short causal window smooths the two-cell output without adding a non-neural policy.
4. The annotated bilateral DNa02/DNg13 rolling activity becomes steering; the same causal smoothing prevents single-tick 0/25/50 Hz jumps.
5. LC4/LPLC2 and DNp01/DNp10 rates are observed.
6. A neural escape readout can reduce throttle and use the neural steering output.
7. Furniture and walls only apply physical collision; they do not select a turn direction.

The dashboard visualizes these rates and shows the active source:

```text
MaleCNS
MaleCNS neural escape
MaleCNS tactile escape
```

## Ablation plan

The next reproducible tests should compare:

| Condition | Expected question |
|---|---|
| Full populations | Does the complete path produce escape output? |
| LC4 silenced | Does fast looming response change? |
| LPLC2 silenced | Does angular-size response change? |
| DNp01 silenced | Does the escape command disappear? |
| DNp10 silenced | Is there a measurable complementary output? |
| DNa02 left/right separated | Does bilateral imbalance predict steering? |
| DNg100 silenced | Does forward motion fall? |

Every run should record raw group rates, applied command, control source, contact object, collision count, and distance. A successful video alone is not sufficient evidence.
