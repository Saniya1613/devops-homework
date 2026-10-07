const { createApp, APP_VERSION } = require('./app');

const PORT = Number(process.env.PORT) || 3000;

createApp().listen(PORT, () => {
  console.log(`session16-cicd-demo v${APP_VERSION} listening on port ${PORT}`);
});
