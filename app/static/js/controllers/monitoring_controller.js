// monitoring_controller.js: Frontend controller for the monitoring page
// This file coordinates the model and view for the monitoring page.

export class MonitoringController {
    constructor(model, view) {
        this.model = model;
        this.view = view;
    }

    async init() {
        const data = await this.model.fetchData();
        this.view.render(data);
    }
}
