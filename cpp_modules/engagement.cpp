#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>


namespace py = pybind11;

/**
 * FocusFlow Engagement Vector Calculator
 *
 * PURPOSE: Compute a weighted engagement score from multiple signals.
 * This demonstrates C++ proficiency for performance-critical calculations.
 *
 * INPUTS:
 *   - gaze_score: 0.0-1.0 (1.0 = looking at screen)
 *   - emotion_score: 0.0-1.0 (1.0 = positive/engaged emotion)
 *   - head_stability: 0.0-1.0 (1.0 = stable, not distracted)
 *
 * OUTPUT:
 *   - Engagement score: 0.0-100.0
 *
 * ALGORITHM:
 *   Uses weighted geometric mean to avoid zero-inflation
 *   (if any signal is 0, the score drops significantly)
 */
double calculate_engagement_score(double gaze_score, double emotion_score,
                                  double head_stability) {
  // Weights (must sum to 1.0)
  const double W_GAZE = 0.5;      // Gaze is most important
  const double W_EMOTION = 0.3;   // Emotion matters
  const double W_STABILITY = 0.2; // Head movement is secondary

  // Clamp inputs to [0, 1]
  gaze_score = std::max(0.0, std::min(1.0, gaze_score));
  emotion_score = std::max(0.0, std::min(1.0, emotion_score));
  head_stability = std::max(0.0, std::min(1.0, head_stability));

  // Weighted geometric mean (more sensitive to low values)
  double engagement = std::pow(gaze_score, W_GAZE) *
                      std::pow(emotion_score, W_EMOTION) *
                      std::pow(head_stability, W_STABILITY);

  // Scale to 0-100
  return engagement * 100.0;
}

/**
 * Batch Processing Version
 * Processes multiple frames efficiently
 */
std::vector<double>
calculate_engagement_batch(const std::vector<double> &gaze_scores,
                           const std::vector<double> &emotion_scores,
                           const std::vector<double> &head_stability_scores) {
  size_t n = gaze_scores.size();
  std::vector<double> results(n);

  for (size_t i = 0; i < n; ++i) {
    results[i] = calculate_engagement_score(gaze_scores[i], emotion_scores[i],
                                            head_stability_scores[i]);
  }

  return results;
}

// Python Bindings
PYBIND11_MODULE(engagement_cpp, m) {
  m.doc() = "FocusFlow C++ Engagement Calculator";

  m.def("calculate_engagement_score", &calculate_engagement_score,
        "Calculate engagement score from vision signals", py::arg("gaze_score"),
        py::arg("emotion_score"), py::arg("head_stability"));

  m.def("calculate_engagement_batch", &calculate_engagement_batch,
        "Batch process engagement scores", py::arg("gaze_scores"),
        py::arg("emotion_scores"), py::arg("head_stability_scores"));
}
