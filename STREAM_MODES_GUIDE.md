# 🛸 UFO Tracker - Stream Modes Guide

## **Simplified Streaming Architecture**

### **✅ What We Fixed**
- **Eliminated confusing mode switching** - No more toggle between MJPEG/frame modes
- **MJPEG is now the default** for live viewing (provides natural motion)
- **Frame refresh only used** for camera controls (immediate feedback on setting changes)
- **Cleaner interface** with purpose-built sections

### **📹 Live Camera View**
**Location:** `📹 Live Cameras` tab
**Stream Type:** MJPEG (continuous video)
**Features:**
- 🎥 **Real-time motion** - Natural video streaming
- 🔄 **Stream refresh** - Restart stream if needed
- 📸 **Frame capture** - Download individual frames
- 🖼️ **Fullscreen** - Click image or use fullscreen button

### **⚙️ Camera Controls View** 
**Location:** `⚙️ Camera Controls` tab
**Stream Type:** Frame refresh (for immediate setting feedback)
**Features:**
- 👀 **Live preview** - See changes as you adjust settings
- ⚡ **Instant feedback** - Preview updates when sliders move
- 🎚️ **Manual controls** - Exposure, gain, brightness, contrast
- ✅ **Apply settings** - Push changes to live stream

### **📚 Advanced Processing Views**
**Image Stacking:**
- Combines multiple frames for noise reduction
- Configurable stack count (2-20 frames)
- Save processed images

**🎯 Feature Alignment:**
- Aligns IR and HQ cameras using computer vision
- Multiple algorithms (ORB, SIFT, SURF, Phase Correlation)
- Show feature detection points
- Real-time alignment processing

## **🔧 Technical Benefits**

### **Stream Performance:**
- **MJPEG streams:** Efficient, browser-native video
- **Frame endpoints:** Fast, single-shot captures
- **Reduced bandwidth:** Only one stream type per use case

### **User Experience:**
- **Intuitive:** Live view = motion, Controls = immediate feedback
- **Mobile-friendly:** Touch targets, responsive design
- **Professional:** Advanced processing without complexity

### **System Architecture:**
```
Live View → MJPEG Stream (/ir_feed, /hq_feed)
    ↓
Controls → Frame Refresh (/ir_frame, /hq_frame)
    ↓
Processing → OpenCV Analysis (stacking, alignment)
```

## **📱 Mobile Usage**
- **Tap streams** for fullscreen viewing
- **Swipe between tabs** for different functions
- **Pinch to zoom** on fullscreen streams
- **Touch controls** optimized for mobile

## **🎯 Use Cases**

### **Live Monitoring:**
1. Go to `📹 Live Cameras`
2. Watch continuous MJPEG streams
3. Use fullscreen for detailed viewing

### **Setting Adjustments:**
1. Go to `⚙️ Camera Controls`
2. Adjust sliders (brightness, exposure, etc.)
3. See immediate preview changes
4. Click "Apply" to update live stream

### **Advanced Processing:**
1. Use `📚 Image Stacking` for noise reduction
2. Use `🎯 Feature Aligned` for camera calibration
3. Save processed images for analysis

This simplified approach eliminates the confusion of multiple modes while providing the right tool for each specific task!
