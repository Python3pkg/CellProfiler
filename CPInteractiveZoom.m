function CPInteractiveZoom
%
% zoom2cursor, without arguments, will activate the current axis, create a text box showing the
% current position of the mouse pointer (similar to pixval), and automatically zoom the image to the
% location of the cursor  as it is moved. The zoomed display dynamically scrolls with the motion of the cursor.
%
% By default, the function zooms to 50% of the image in the axis.
%
% BUTTON CLICKS:
% Left-clicking will zoom in further, and right-clicking will zoom out.
% Shift-clicking (or simultaneously clicking the left and right mouse buttons) at any point
% will display the original (un-zoomed) image, as will moving the
% cursor outside of the current axis. The zoom percentage is restored when the mouse is moved.
% Double-clicking zooms out to the original image, modifying the zoom percentage.
%
% Tested under R12.1 and R13.
%
% Written by Brett Shoelson, Ph.D. (shoelson@helix.nih.gov, shoelson@hotmail.com)
% 12/26/02
% 2/16/03; Rev 2: Program is more robust; fixes a bug when window is resized.
%                 Incremental increase/decrease in zoom percent (on mouseclick) has been reduced.
%                 Also: Now works with images, surfaces, lines (and thus
%                 plots), and patches (rather than just images)
% 6/27/05; Rev 3 (Colin Clarke): Fixed clash with normal zoom function, allows zoom for
%                 multiple images in one figure, and made it go better with
%                 CellProfiler.

currfig = findobj('type','figure');
if isempty(currfig)
    beep;
    h=warndlg('There are no figures open!');
    uiwait(h);
    return
end
currfig = currfig(1);
figure(currfig);
zoomparams.currax = gca;
if isempty(zoomparams.currax)
    error('The current figure contains no axes!');
end


%Precedence: Images, surfaces, lines, patches
%Are there any images in the current axes?

images=findobj(currfig,'type','image');


zoomparams.pct = 0.5; %Default value


zoomparams.oldpointer = get(currfig,'pointer');
set(currfig, 'Pointer', 'crosshair');
axes(zoomparams.currax);

currax = get(zoomparams.currax);
zoomparams.refax = copyobj(zoomparams.currax,gcf);

% For simplicity, I store the bdfunction in both the current axis AND the current object. For images, it makes sense to
% store it in the object (since the object covers the axis). For other objects (like lines), storing in the object forces
% a click directly on the line/point, but storing in the axis only means a click on the line does not trigger the callback.
warning off; %I turn this off because of the annoying (but erroneous)"Unrecognized OpenGL" message.
set(zoomparams.currax,'buttondownfcn','feval(getappdata(gcf,''bdfcnhandle''));','busyaction','queue');
set(images,'buttondownfcn','feval(getappdata(gcf,''bdfcnhandle''));','busyaction','queue');

set(findobj(zoomparams.refax,'type','children'),'handlevisibility','on');
set(zoomparams.refax,'visible','off');
axes(zoomparams.refax);
cla;

zoomparams.oldaxunits = get(zoomparams.currax,'units');
zoomparams.ydir = get(zoomparams.currax,'ydir');

zoomparams.oldxlim = get(zoomparams.currax,'xlim');
zoomparams.oldylim = get(zoomparams.currax,'ylim');
zoomparams.oldzlim = get(zoomparams.currax,'zlim');
zoomparams.dbold = get(currfig,'doublebuffer');
zoomparams.xrange = diff(zoomparams.oldxlim);
zoomparams.yrange = diff(zoomparams.oldylim);
zoomparams.zrange = diff(zoomparams.oldzlim);
zoomparams.xdist = zoomparams.pct*zoomparams.xrange;
zoomparams.ydist = zoomparams.pct*zoomparams.yrange;
zoomparams.zdist = zoomparams.pct*zoomparams.zrange;
zoomparams.oldwbmf = get(currfig,'windowbuttonmotionfcn');


setappdata(currfig, 'zoomfcnhandle', @zoomfcn);
setappdata(gcf, 'bdfcnhandle',@bdfcn);
%%% Determines screen resolution so the display box is positioned properly.
PointsPerPixel = 72/get(0,'ScreenPixelsPerInch');
FigurePosition = get(gcf, 'Position');

set(currfig,'doublebuffer','on','windowbuttonmotionfcn','feval(getappdata(gcf,''zoomfcnhandle''));');
endbutton = uicontrol('style','pushbutton','string','X',...
    'foregroundcolor',[0.7 0.7 0.7],'backgroundcolor','k',...
    'Position',PointsPerPixel*[FigurePosition(3)-180 0 20 28],...
    'fontweight','b','callback',...
    ['zoomparams = getappdata(gcf,''zoomparams'');set(gcf,''windowbuttonmotionfcn'','''');',...
    'set(zoomparams.currax,''units'',zoomparams.oldaxunits,''xlim'',zoomparams.oldxlim,''ylim'',zoomparams.oldylim);',...
    'set(get(zoomparams.currax,''children''),''buttondownfcn'','''');',...
    'set(gcf,''pointer'',zoomparams.oldpointer,''doublebuffer'',zoomparams.dbold);',...
    'delete(zoomparams.dispbox1);delete(zoomparams.dispbox2);delete(gcbo);delete(findobj(''Type'',''axes'',''Visible'',''off''));clear zoomparams;']);
zoomparams.dispbox1 = uicontrol('style','frame',...
    'backgroundcolor','k',...
    'Position',PointsPerPixel*[FigurePosition(3)-160 0 165 27]);
msgstr = sprintf('x = %3.0f;  y = %3.0f',0,0);

zoomparams.dispbox2 = uicontrol('style','text',...
    'backgroundcolor','k','foregroundcolor',[0.7 0.7 0.7],...
	'Position',PointsPerPixel*[FigurePosition(3)-158 3 159 22],...
    'string',msgstr,...
    'horizontalalignment','center');
setappdata(gcf,'zoomparams',zoomparams);
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

function zoomfcn
zoomparams = getappdata(gcf,'zoomparams');
children = get(zoomparams.currax,'Children');
if isempty(children) || ~any(strcmp(get(children,'Type'),'image'))
    return;
end
posn = get(zoomparams.refax,'currentpoint');
posn = posn(1,:);

x = posn(1,1);
y = posn(1,2);
z = posn(1,3);

        % x and y are already in expressed in proper pixel coordinates
        x1 = min(max(1,x-0.5*zoomparams.xdist),zoomparams.xrange-zoomparams.xdist) + 0.5;
        y1 = min(max(1,y-0.5*zoomparams.ydist),zoomparams.yrange-zoomparams.ydist) + 0.5;
        z1 = min(max(1,z-0.5*zoomparams.zdist),zoomparams.zrange-zoomparams.zdist) + 0.5;
        x2 = x1 + zoomparams.xdist;
        y2 = y1 + zoomparams.ydist;
        z2 = z1 + zoomparams.zdist;
 

if x >= zoomparams.oldxlim(1) && x <= zoomparams.oldxlim(2) && ...
        y >= zoomparams.oldylim(1) && y <= zoomparams.oldylim(2) && ...
    z >= zoomparams.oldzlim(1) && z <= zoomparams.oldzlim(2)
    set(zoomparams.dispbox2,'string',sprintf('x = %3.2f;  y = %3.2f',x,y));
    set(zoomparams.currax,'xlim',[x1 x2],'ylim',[y1 y2]);
else
    set(zoomparams.dispbox2,'string',sprintf('x = %3.0f;  y = %3.0f',0,0));
    set(zoomparams.currax,'xlim',zoomparams.oldxlim,'ylim',zoomparams.oldylim);
end

%Note: up to this point, the only thing that has changed in refax is the currentpoint property
return

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function bdfcn
zoomparams = getappdata(gcf,'zoomparams');
% SelectionType
% normal: Click left mouse button
% extend: Shift - click left mouse button or click both left and right mouse buttons
% alt: Control - click left mouse button or click right mouse button
% open: Double click any mouse button
zoomparams;
tempax = gca;
if zoomparams.currax~=tempax
    zoomparams.currax = gca;
    zoomparams.oldxlim = get(zoomparams.currax,'xlim');
    zoomparams.oldylim = get(zoomparams.currax,'ylim');
    zoomparams.oldzlim = get(zoomparams.currax,'zlim');
    zoomparams.xrange = diff(zoomparams.oldxlim);
    zoomparams.yrange = diff(zoomparams.oldylim);
    zoomparams.zrange = diff(zoomparams.oldzlim);
    zoomparams.xdist = zoomparams.pct*zoomparams.xrange;
    zoomparams.ydist = zoomparams.pct*zoomparams.yrange;
    zoomparams.zdist = zoomparams.pct*zoomparams.zrange;
    zoomparams.pct = .5;
    delete(zoomparams.refax);
    zoomparams.refax = copyobj(zoomparams.currax,gcf);
    set(findobj(zoomparams.refax,'type','children'),'handlevisibility','on');
    set(zoomparams.refax,'visible','off');
    axes(zoomparams.refax);
    cla;
    setappdata(gcf,'zoomparams',zoomparams);
end

switch get(gcf,'selectiontype')
case 'normal'
	zoomparams.pct = max(0.01,zoomparams.pct*0.9);
case 'alt'
	zoomparams.pct = min(1,zoomparams.pct*1.1);
case 'extend'
	set(zoomparams.currax,'xlim',zoomparams.oldxlim,'ylim',zoomparams.oldylim,'zlim',zoomparams.oldzlim);
case 'open'
	zoomparams.pct = 1;
end

zoomparams.xdist = zoomparams.pct*zoomparams.xrange;
zoomparams.ydist = zoomparams.pct*zoomparams.yrange;
zoomparams.zdist = zoomparams.pct*zoomparams.zrange;


if ~strcmp(get(gcf,'selectiontype'),'extend')
    setappdata(gcf,'zoomparams',zoomparams);
    feval(getappdata(gcf,'zoomfcnhandle'));
end
return
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
