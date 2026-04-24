# 🎲 The Entropy Challenge

[🇬🇧 Read in English](README.md) | [🇹🇷 Türkçe Oku](README.tr.md)

## Introduction
We have developed a next-generation random number generator that processes **Radio Frequency (RF) Noise** through a proprietary **Neural Network architecture**, followed by SHA-3 post-processing. We claim this source provides **True Randomness** quality, indistinguishable from ideal noise sources.

We are releasing the outputs and the verification reports—but **not the source code**. The challenge is simple: **Prove us wrong.**

## The Data
- **Sample File:** `data/random_sample.bin` (~17 MB)
- **Quality:** Validated against **NIST STS (SP 800-22)** and **NIST SP 800-90B**.
- **Entropy:** >0.999 bits/bit.

Detailed reports can be found in [NIST_REPORT.md](NIST_REPORT.md).

## 🏆 The Challenge
We are offering a bounty to anyone who can successfully "break" this generator.

### Categories & Recognition

#### 🥇 Level 1: The Predictor - Next Bit Test
**Reward:** **Hall of Fame Entry & Certificate of Achievement**
**Task:** Given a sequence of $N$ bits from our source, accurately predict the $N+1$ bit with a probability significantly greater than 50% (Statistical significance $p < 0.001$).

#### 🥈 Level 2: The Distinguisher
**Reward:** **Honorable Mention**
**Task:** Create an algorithm that can distinguish our output from `os.urandom` or hardware TRNGs with an advantage $> 0.01$.

#### 🥉 Level 3: Pattern Finder
**Reward:** **Acknowledgment**
**Task:** Identify a repeating period or a significant bias in the provided binary sample that was missed by standard NIST tests.

## How to Submit
1. Fork this repository.
2. Create your analysis script (Python/C/Matlab).
3. Open an Issue with your findings and proof.
4. If verifiable, you will be added to our **Hall of Fame**.

## 🏅 Hall of Fame
| Date | Researcher | Achievement |
|------|------------|-------------|
| - | - | - |

---
*Powered by Deep Neural Stochastic Processes & Keccak*
