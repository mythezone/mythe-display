# Display Output Options on Ubuntu

Date: 2026-06-03

Goal: determine whether an Ubuntu PC can output video to a chassis secondary screen through USB, and define fallback choices.

## Short Answer

If the motherboard USB-C port is only a normal data port, it cannot output native video to a USB-C monitor by software configuration alone.

For USB single-cable video, one of these must be true:

- The USB-C source port supports DisplayPort Alt Mode, USB4, or Thunderbolt video routing.
- The screen/dock/adapter contains a DisplayLink-style USB graphics chip and Ubuntu has a compatible driver.
- The screen is not a video monitor at all, but a protocol-specific USB smart screen, such as supported Turing/XuanFang/TURZX panels.

Otherwise, use HDMI/DisplayPort from the GPU or motherboard display output.

## Why Data-only USB-C Cannot Become Video

VESA describes DisplayPort Alt Mode as a mode where USB-C repurposes high-speed lanes to carry DisplayPort audio/video while also allowing USB data and power in supported configurations. Video source devices that support DisplayPort Alt Mode can drive DisplayPort/HDMI/DVI/VGA adapters.

Source: [VESA DisplayPort Alt Mode announcement](https://vesa.org/featured-articles/vesa-brings-displayport-to-new-usb-type-c-connector/)

Practical implication:

- USB-C connector shape is not enough.
- Host port, cable, and display/adapter path must all support the video mode.
- If the mainboard manual identifies the port only as USB data, it should be treated as non-video.

## Option Matrix

| Option | Works as normal Ubuntu monitor | Cable count | Reliability | Notes |
| --- | --- | --- | --- | --- |
| HDMI/DisplayPort panel | Yes | Usually HDMI + power, sometimes one cable if powered separately inside case | Highest | Recommended default. |
| USB-C DP Alt Mode panel | Yes | One USB-C cable for video/power if power budget is enough | High when hardware supports it | Requires source port with DP Alt Mode/USB4/Thunderbolt. |
| DisplayLink USB monitor/adapter | Yes, through USB graphics driver | One USB cable or USB + power | Medium | Uses DisplayLink chip and driver; not native GPU output. |
| Turing/XuanFang/TURZX USB smart screen | No, protocol-specific framebuffer/control | One USB cable | Medium-high for supported models | Use library renderer; not a normal desktop monitor. |
| Data-only USB-C to HDMI/USB-C monitor | No | N/A | Not viable | Passive adapters need Alt Mode; software cannot add missing GPU lane routing. |

## DisplayLink on Ubuntu

DisplayLink is the practical workaround when the host has no native USB-C video path but the display/adapter includes a USB graphics chipset.

Official Synaptics DisplayLink Ubuntu page currently lists the latest official Ubuntu driver as Release 6.2 from 2025-09-11, prepared for Ubuntu 20.04, 22.04, 23.04, and 24.04.

Source: [Synaptics DisplayLink Ubuntu downloads](https://drivers.synaptics.com/products/displaylink-graphics/downloads/ubuntu)

Important caveats:

- It is a driver-dependent path, not native GPU output.
- Secure Boot may require DKMS/MOK module signing flow. Ubuntu documents MOK handling for third-party DKMS modules under Secure Boot.
- Compatibility must be rechecked for Ubuntu versions newer than those listed by Synaptics.
- DisplayLink can add CPU overhead and latency, which is usually acceptable for a static metrics panel but not ideal for animation-heavy content.

Source: [Ubuntu Secure Boot documentation](https://documentation.ubuntu.com/security/docs/security-features/platform-protections/secure-boot/), [DisplayLink Secure Boot support article](https://support.displaylink.com/knowledgebase/articles/1181617-how-to-use-displaylink-ubuntu-driver-with-uefi-sec)

## USB Smart Screens

Some small case screens are sold as USB-C screens but are not generic video monitors. They often use USB serial/HID protocols and vendor-specific drawing commands. Turing Smart Screen Python is useful here because it abstracts several supported screen protocols and can render themes/metrics directly.

Source: [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)

This path can be good for tiny 3.5-inch panels, but it conflicts with the requirement to use the display as a normal Ubuntu video output. The app would need a separate renderer backend that draws frames or commands to the device protocol.

## Recommended Hardware Path

Recommended for the first implementation:

1. Use HDMI or DisplayPort to a small internal monitor.
2. Power it from internal USB/SATA/Molex as appropriate.
3. Let Ubuntu detect it as a normal second monitor.
4. Run Mythe Display full-screen on that monitor.

Recommended if one cable is mandatory:

1. Verify motherboard manual for USB-C DP Alt Mode, USB4, or Thunderbolt support.
2. If unsupported, use a DisplayLink display/adapter and pin Ubuntu/driver compatibility.
3. Avoid ordinary USB-C-to-HDMI adapters on data-only ports.

Useful verification steps on the real machine:

- Check motherboard manual and rear I/O labeling for DP/Thunderbolt/USB4 symbols.
- Test with a known-good USB-C DP Alt Mode monitor and full-featured cable.
- In Ubuntu display settings, confirm whether the display appears as a normal monitor.
- For DisplayLink, confirm the adapter appears in `lsusb` and the DisplayLink/evdi driver is loaded.

## Implication for Mythe Display

The application should not depend on a USB transport. It should render to a normal browser/window first. Hardware-specific output adapters can be added later:

- `video-monitor`: default browser/Electron fullscreen renderer.
- `displaylink-monitor`: same as normal monitor after driver installation.
- `turing-smart-screen`: optional protocol renderer for supported USB smart screens.
