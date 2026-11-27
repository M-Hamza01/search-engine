"""Generate data/sample_arxiv.jsonl, a small test file in the arXiv metadata format.

It contains
* the two REAL records from the Kaggle arXiv file that we inspected, and
* N synthetic records (id prefix "synthetic-") built from topic word pools so the
  index has realistic overlap between documents.  They are NOT real papers.

For testing against real data, simply take the first lines of the Kaggle file:
    head -n 1000 arxiv-metadata-oversnapshot.json > data/real_arxiv_1000.jsonl
"""

import json
import os
import random

REAL_RECORDS = [
    {"id": "1608.01482", "title": "Derived coisotropic structures I: affine case",
     "authors": "Valerio Melani and Pavel Safronov", "categories": "math.AG math.SG",
     "journal_ref": "Selecta Math. 24 (2018), pp. 3061-3118", "update_date": "2018-10-03", "versions": 3,
     "abstract": "We define and study coisotropic structures on morphisms of commutative dg algebras in the context of shifted Poisson geometry, i.e. $P_n$-algebras. Roughly speaking, a coisotropic morphism is given by a $P_{n+1}$-algebra acting on a $P_n$-algebra. One of our main results is an identification of the space of such coisotropic structures with the space of Maurer--Cartan elements in a certain dg Lie algebra of relative polyvector fields. To achieve this goal, we construct a cofibrant replacement of the operad controlling coisotropic morphisms by analogy with the Swiss-cheese operad which can be of independent interest. Finally, we show that morphisms of shifted Poisson algebras are identified with coisotropic structures on their graph."},
    {"id": "2106.11502", "title": "Measuring Violations of Positive Involvement in Voting",
     "authors": "Wesley H. Holliday (University of California, Berkeley), Eric Pacuit (University of Maryland)",
     "categories": "cs.GT cs.MA econ.TH", "journal_ref": "EPTCS 335, 2021, pp. 189-209",
     "update_date": "2021-06-23", "versions": 1,
     "abstract": "In the context of computational social choice, we study voting methods that assign a set of winners to each profile of voter preferences. A voting method satisfies the property of positive involvement (PI) if for any election in which a candidate x would be among the winners, adding another voter to the election who ranks x first does not cause x to lose. Surprisingly, a number of standard voting methods violate this natural property. In this paper, we investigate different ways of measuring the extent to which a voting method violates PI, using computer simulations. We consider the probability (under different probability models for preferences) of PI violations in randomly drawn profiles vs. profile-coalition pairs (involving coalitions of different sizes). We argue that in order to choose between a voting method that satisfies PI and one that does not, we should consider the probability of PI violation conditional on the voting methods choosing different winners. We should also relativize the probability of PI violation to what we call voter potency, the probability that a voter causes a candidate to lose. Although absolute frequencies of PI violations may be low, after this conditioning and relativization, we see that under certain voting methods that violate PI, much of a voter's potency is turned against them - in particular, against their desire to see their favorite candidate elected."},
]

TOPICS = {
    "cs.IR": "retrieval ranking query search index relevance documents recall precision embedding semantic corpus engine".split(),
    "cs.DS": "algorithm graph tree hash complexity sorting dynamic amortized bound heap trie structure runtime".split(),
    "math.AG": "algebraic variety cohomology scheme morphism sheaf derived moduli curve stack category functor".split(),
    "cs.GT": "voting equilibrium auction mechanism preference winner coalition strategy social choice election utility".split(),
    "stat.ML": "learning model regression kernel bayesian gradient sampling variance neural classification training".split(),
    "physics.optics": "photon laser waveguide resonator nonlinear dispersion fiber spectrum quantum coherence pulse".split(),
    "cs.CL": "language translation corpus parsing syntax semantic embedding sentence token grammar word vocabulary".split(),
}
GLUE = ("we the of and in a show propose results approach paper also method for that is with novel using "
        "analysis new can based our this which these on to by an study present within between under").split()
FIRST = "Ali Sara Omar Hina Bilal Zara Usman Maryam Farhan Ayesha Daniel Elena Wei Mei Ivan Lucia".split()
LAST = "Khan Ahmed Raza Malik Chen Wang Petrov Rossi Novak Silva Okafor Tanaka Haddad Berg Ortiz Shah".split()


def sentence(rng, primary, secondary):
    words = []
    for _ in range(rng.randint(10, 20)):
        r = rng.random()
        if r < 0.45:
            words.append(rng.choice(TOPICS[primary]))
        elif r < 0.52:
            words.append(rng.choice(TOPICS[secondary]))
        else:
            words.append(rng.choice(GLUE))
    return " ".join(words).capitalize() + "."


def make_record(rng, n):
    primary, secondary = rng.choice(list(TOPICS)), rng.choice(list(TOPICS))
    title = " ".join(rng.choice(TOPICS[primary]) for _ in range(rng.randint(3, 6)))
    title = title.capitalize() + (" for " + rng.choice(TOPICS[secondary]) if rng.random() < 0.5 else "")
    authors = " and ".join(f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(rng.randint(1, 4)))
    abstract = " ".join(sentence(rng, primary, secondary) for _ in range(rng.randint(6, 11)))
    cats = primary + ("" if primary == secondary else " " + secondary)
    return {"id": f"synthetic-{n:04d}", "title": title, "authors": authors, "categories": cats,
            "journal_ref": None, "update_date": f"{rng.randint(2008, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "versions": rng.randint(1, 4), "abstract": abstract}


def main(count=400, out="data/sample_arxiv.jsonl", seed=250):
    rng = random.Random(seed)
    records = REAL_RECORDS + [make_record(rng, i) for i in range(count)]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} records to {out}")


if __name__ == "__main__":
    main()
