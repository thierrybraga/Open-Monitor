// analytics_controller.js: Frontend controller for the analytics page
// This file coordinates the model and view for the analytics page.

export class AnalyticsController {
    constructor(model, view) {
        this.model = model;
        this.view = view;
    }

    async init() {
        const data = await this.model.fetchData();
        this.view.render(data);
    }
}
