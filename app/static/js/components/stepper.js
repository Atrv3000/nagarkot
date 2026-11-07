/**
 * Nagarkot Access Control Service - Stepper Component
 * Renders a horizontal workflow stepper visualizing shipment lifecycle.
 */

export function createJobStepper(job) {
  const container = document.createElement("div");
  container.className = "job-stepper-container";

  const standardStages = [
    { key: "CONFIRMED", label: "Confirmed", actorKey: null },
    { key: "PREPARED", label: "Prepared", actorKey: "prepared_by" },
    { key: "CHECKED", label: "Checked", actorKey: "checked_by" },
    { key: "FILED", label: "Filed", actorKey: "filed_by" },
  ];

  const currentStage = job.stage;
  const isSpecialState = currentStage === "CANCELLED" || currentStage === "REOPENED";

  const stepper = document.createElement("div");
  stepper.className = "job-stepper";

  const stageOrder = ["CONFIRMED", "PREPARED", "CHECKED", "FILED"];
  const currentIdx = stageOrder.indexOf(currentStage);

  standardStages.forEach((st, idx) => {
    const stepEl = document.createElement("div");
    let stateClass = "step-upcoming";

    if (!isSpecialState) {
      if (idx < currentIdx) {
        stateClass = "step-completed";
      } else if (idx === currentIdx) {
        stateClass = "step-current";
      }
    } else {
      // In cancelled or reopened state, show prior completed milestones
      if (currentStage === "CANCELLED") {
        stateClass = "step-neutral";
      } else if (currentStage === "REOPENED") {
        if (st.key === "CONFIRMED") stateClass = "step-completed";
        else stateClass = "step-upcoming";
      }
    }

    stepEl.className = `stepper-step ${stateClass}`;

    // Step circle/indicator
    const circle = document.createElement("div");
    circle.className = "step-circle";
    if (stateClass === "step-completed") {
      circle.textContent = "✓";
    } else {
      circle.textContent = String(idx + 1);
    }

    // Step details
    const textGroup = document.createElement("div");
    textGroup.className = "step-text-group";

    const label = document.createElement("div");
    label.className = "step-label";
    label.textContent = st.label;

    textGroup.appendChild(label);

    if (st.actorKey && job[st.actorKey]) {
      const actor = document.createElement("div");
      actor.className = "step-actor";
      actor.textContent = job[st.actorKey];
      textGroup.appendChild(actor);
    }

    stepEl.appendChild(circle);
    stepEl.appendChild(textGroup);
    stepper.appendChild(stepEl);

    // Connector line between steps
    if (idx < standardStages.length - 1) {
      const line = document.createElement("div");
      line.className = `step-connector ${stateClass === 'step-completed' && currentIdx > idx ? 'connector-active' : ''}`;
      stepper.appendChild(line);
    }
  });

  container.appendChild(stepper);

  // If special state, show an alert banner below stepper
  if (isSpecialState) {
    const alert = document.createElement("div");
    alert.className = `special-state-alert special-state-${currentStage.toLowerCase()}`;
    if (currentStage === "CANCELLED") {
      alert.textContent = "This shipment was cancelled prior to customs filing.";
    } else if (currentStage === "REOPENED") {
      alert.textContent = `This shipment was formally reopened for amendment (Cycle: ${job.cycle}).`;
    }
    container.appendChild(alert);
  }

  return container;
}
