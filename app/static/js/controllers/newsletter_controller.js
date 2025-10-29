// newsletter_controller.js: Frontend controller for the newsletter page
// This file coordinates the model and view for the newsletter page.

export class NewsletterController {
    constructor(model, view) {
        this.model = model;
        this.view = view;
    }

    async init() {
        const data = await this.model.fetchData();
        this.view.render(data);
    }
}
