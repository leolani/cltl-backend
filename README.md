# cltl-backend

Backend services for the Leolani platform.

This repository is a component of the [Leolani framework](https://github.com/leolani/cltl-combot).
For usage of the component within the framework see the instructions there.

## Backend Architecture

![Backend - Architectur](doc/Backend.png)


#### Backend layer

The Backend Container connects to the backend server to retrieve raw signals and processes them to
make them available in the application. This involves:
* Managing access to the signal resources (e.g. mute mic while speaking).
* Store raw signal data.
* Publish events for the incoming signals, pointing to the storage location where the raw data can be retrieved.
* Subscribe to events that result in outgoing signals and send them to the backend server.

### Backend Server

The application is composed of the following components:
The Backend Server is a standalone application that provides a REST API with the basic raw signals.

#### Storage

The Backend stores the signal data separately and provides access to the stored
signals over a REST API.


## Contributing

Contributions are what make the open source community such an amazing place to be learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


<!-- LICENSE -->
## License

Distributed under the MIT License. See [`LICENSE`](https://github.com/leolani/cltl-combot/blob/main/LICENCE) for more information.

<!-- CONTACT -->
## Authors

* [Taewoon Kim](https://tae898.github.io/)
* [Thomas Baier](https://www.linkedin.com/in/thomas-baier-05519030/)
* [Selene Báez Santamaría](https://selbaez.github.io/)
* [Piek Vossen](https://github.com/piekvossen)
