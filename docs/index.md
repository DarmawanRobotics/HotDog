---
layout: home
title: HotDog
titleTemplate: Substation patrol on the Lynx M20
hero:
  name: HotDog
  text: Substation patrol on the Lynx M20
  tagline: Teach a round once. The robot then walks it on its own odometry, stops at every piece of equipment and checks it for overheating and partial discharge. A watchdog brings it home, reports open in the browser, alerts reach Telegram.
  image:
    src: /logo.png
    alt: HotDog
  actions:
    - theme: brand
      text: Get started
      link: /overview
    - theme: alt
      text: User Manual
      link: /manual/user-manual
    - theme: alt
      text: GitHub
      link: https://github.com/DarmawanRobotics/HotDog
features:
  - title: Teach and repeat, no map
    details: Routes are driven once from the dock with the M20 remote and repeated on the robot's own odometry. Nothing is mapped; the dock is the origin, re-anchored before every patrol.
  - title: Overheat analysis
    details: The UniPod MT11 measures every target against fixed limits, the air temperature and the other phases of the same equipment (NETA MTS), and keeps the thermal and visible images.
  - title: Partial discharge
    details: Once the robot has stopped, the Hertzinno HZ-FA-371 listens at acoustic targets for corona, surface and floating discharge, and keeps the sound map and the PRPD.
  - title: A watchdog that brings it home
    details: A low battery, an overlong patrol or a blocked robot sends it back to the dock along the taught route. An operator, the e-stop or the M20 remote always comes first.
  - title: Reports in the browser
    details: Every patrol is a page on port 8088 with each finding against the last round and its evidence, day and front pages, and retention by age and free space.
  - title: Alerts on Telegram
    details: Warning and critical findings with their image, failed and finished patrols and health errors reach the crew in English or Bahasa Indonesia, kept on disk while offline.
---

<figure class="home-shot">
  <img src="./manual/img/system.png" alt="HotDog: the Lynx M20 with two RoboSense Airy, the UniPod MT11 and the HZ-FA-371, the payload computer running Dharma and HotDog, the operator, reports and alerts" />
  <figcaption>The Lynx M20 with its LiDARs, pod and acoustic camera; the payload computer runs Dharma and HotDog.</figcaption>
</figure>

<div class="home-guides">
  <div class="home-guide">
    <h3>User Manual</h3>
    <p>For operators: safety in the substation, teaching routes and targets, patrols, results and alerts. No robotics needed.</p>
    <div class="links"><a href="./manual/user-manual">Read</a><a href="./HotDog-User-Manual.pdf" target="_blank">PDF</a></div>
  </div>
  <div class="home-guide">
    <h3>Technician Guide</h3>
    <p>For technicians: configuration layers, the M20, LiDARs and the protective field, inspection limits, maintenance, every parameter.</p>
    <div class="links"><a href="./technician/technician-guide">Read</a><a href="./HotDog-Technician-Guide.pdf" target="_blank">PDF</a></div>
  </div>
  <div class="home-guide">
    <h3>Site Acceptance Test</h3>
    <p>For the handover at a substation: safety functions, navigation, inspection, reports and alerts, resilience, sign-off.</p>
    <div class="links"><a href="./acceptance/acceptance-test">Read</a><a href="./HotDog-Site-Acceptance-Test.pdf" target="_blank">PDF</a></div>
  </div>
</div>
