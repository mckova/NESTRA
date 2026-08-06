from benchmarks.nestra_oracle.lib import (
    aggregate_methods,
    answer_metrics,
    bm25_rank,
    enforce_answer_contract,
)


def test_bm25_ranks_query_evidence_before_noise():
    documents = [
        {"text": "gardens and flowers"},
        {"text": "Sissy Spacek has middle name Elizabeth"},
    ]
    assert bm25_rank("Sissy Spacek middle name", documents)[0] == 1


def test_task_loss_is_one_minus_token_f1():
    metrics = answer_metrics("Mary Elizabeth", "Elizabeth")
    assert metrics["taskLoss"] == 1 - metrics["tokenF1"]


def test_answer_contract_preserves_names_and_bounds_binary():
    assert enforce_answer_contract("Is Alpha related to Beta?", "Yes, because...") == "Yes"
    assert (
        enforce_answer_contract("Who is the actor?", "Sissy Spacek\nExplanation") == "Sissy Spacek"
    )


def test_method_aggregation_reports_quality_latency_and_tokens():
    examples = [
        {
            "systems": {
                "direct": {
                    "quality": {"exactMatch": 1, "tokenF1": 1, "exactLoss": 0, "taskLoss": 0},
                    "latencyMs": 10,
                    "calls": [
                        {
                            "usage": {
                                "inputTokens": 2,
                                "outputTokens": 1,
                                "reasoningTokens": 0,
                                "totalTokens": 3,
                                "cachedInputTokens": 0,
                            }
                        }
                    ],
                }
            }
        }
    ]
    result = aggregate_methods(examples)["direct"]
    assert result["tokenF1"] == 1 and result["averageTokensPerExample"] == 3
