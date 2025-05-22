// chatbot_controller.js: Frontend controller for the chatbot page
// This file coordinates the model and view for the chatbot page.

export class ChatbotController {
    constructor(model, view) {
        this.model = model;
        this.view = view;
    }

    async init() {
        const data = await this.model.fetchData();
        this.view.render(data);
    }
}
