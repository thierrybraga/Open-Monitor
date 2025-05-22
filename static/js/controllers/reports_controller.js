// reports_controller.js: Frontend controller for the reports page
// This file coordinates the model and view for the reports page.

export class ReportsController {
    constructor(model, view) {
        this.model = model;
        this.view = view;
    }

    async init() {
        const data = await this.model.fetchData();
        this.view.render(data);
    }
}
