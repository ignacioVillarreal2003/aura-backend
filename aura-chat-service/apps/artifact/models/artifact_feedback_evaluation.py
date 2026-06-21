from django.db import models


class ArtifactFeedbackEvaluation(models.Model):
    feedback = models.OneToOneField(
        "artifact.ArtifactFeedback",
        on_delete=models.CASCADE,
        related_name="evaluation",
        db_column="feedback_id",
    )
    evaluated_at = models.DateTimeField(auto_now_add=True)
    judge_model = models.CharField(max_length=128)
    failure_category = models.CharField(max_length=64)
    failure_explanation = models.TextField()
    expected_output = models.TextField()
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "artifact_feedback_evaluation"

    def __str__(self):
        return f"Evaluation:{self.id} for feedback:{self.feedback_id} ({self.failure_category})"
